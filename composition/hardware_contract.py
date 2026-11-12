"""Derive GAR JSON from authored parts, wiring and interface intent CSVs.

interfaces.csv contains semantic selections and constraints, never another
copy of GPIO/header numbers. Wiring remains in connections.csv; Linux I/O
assignment remains in the Product's runtime CSVs. No device is contacted.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace

from product import csv_rows, inside, read_json


def from_manifest(root):
    """Contract reading is independent of a Product's native SDK build schema."""
    root = Path(root).resolve()
    data = read_json(root / 'product.json')
    hardware = inside(root, data['hardware']['physical'])
    board = read_json(inside(root, data['components']['board']) / 'board.json')
    return SimpleNamespace(root=root, data=data, board=board, hardware=hardware,
        gpio=csv_rows(hardware/'gpio.csv'), spi=csv_rows(hardware/'spi.csv'),
        i2c=csv_rows(hardware/'i2c.csv') if (hardware/'i2c.csv').is_file() else [])


def one(items, label):
    if len(items) != 1:
        raise ValueError(f"Expected exactly one {label}; found {len(items)}")
    return items[0]


def header_pin(value):
    match = re.fullmatch(r"(?:physical pin )?(\d+)(?:\s*\([^\n]*\)|:[^\n]+)?", value.strip())
    return str(int(match[1])) if match else value.strip()


def derive(product, capabilities):
    settings = product.data['hardware']['contract']
    expected_target = settings.get('target_id', product.board.get('target_id', product.board['id']))
    if capabilities['target_id'] != expected_target:
        raise ValueError('Selected capabilities do not match the Product board/target')
    parts = csv_rows(inside(product.root, settings['components']))
    names = [part['component_id'] for part in parts]
    if len(set(names)) != len(names) or any(not name for name in names):
        raise ValueError('Component IDs must be unique and nonempty')
    board = settings['board_component']
    if board not in names:
        raise ValueError('The wiring board component is missing from components.csv')
    connections = csv_rows(inside(product.root, settings['connections']))
    if any(row['source'] not in names or row['target'] not in names for row in connections):
        raise ValueError('A connection refers to an unknown component')
    interfaces = csv_rows(inside(product.root, settings['interfaces']))
    required_fields = {'id', 'kind', 'component_id', 'runtime_name', 'component_pins', 'required_drivers'}
    for index, interface in enumerate(interfaces, 2):
        if not required_fields <= interface.keys() or any(interface[key] is None for key in required_fields):
            raise ValueError(f'interfaces.csv row {index}: missing columns or cells; require {sorted(required_fields)}')
    requirements, mappings, seen = [], [], set()
    for interface in interfaces:
        identity, kind, component = interface['id'], interface['kind'], interface['component_id']
        if not identity or identity in seen or component not in names or kind not in ('gpio', 'spi', 'i2c', 'video', 'network'):
            raise ValueError(f'Invalid, duplicate or unsupported interface: {identity}')
        seen.add(identity)
        drivers = [value.strip() for value in interface['required_drivers'].split(';') if value.strip()]
        if not drivers or len(set(drivers)) != len(drivers):
            raise ValueError(f'{identity}: declare unique required drivers explicitly')
        requirement = {'id': identity, 'kind': kind, 'component': component, 'required_drivers': drivers}
        if kind in ('gpio', 'spi', 'i2c') or interface.get('voltage_v'):
            voltage = float(interface['voltage_v'])
            if not math.isfinite(voltage) or voltage <= 0:
                raise ValueError(f'{identity}: voltage must be a finite positive number')
            requirement['voltage_v'] = voltage
        runtime = None
        if kind != 'network':
            table = {'gpio': product.gpio, 'spi': product.spi, 'i2c': getattr(product, 'i2c', []),
                     'video': csv_rows(product.hardware / 'video.csv') if (product.hardware / 'video.csv').is_file() else []}[kind]
            runtime = one([row for row in table if row['name'] == interface['runtime_name']], f'{identity} runtime row')
        candidates = [resource for resource in capabilities['resources'] if resource['kind'] == kind]
        if interface.get('resource'):
            candidates = [resource for resource in candidates if resource['id'] == interface['resource']]
        if runtime:
            device = runtime['chip'] if kind == 'gpio' else runtime['dev']
            candidates = [resource for resource in candidates if resource['device'] == device]
        resource = one(candidates, f'{identity} target resource')
        mapping = {'requirement': identity, 'resource': resource['id'], 'pinmux': resource['pinmux']['id']}
        pins = []
        for selection in interface['component_pins'].split(';'):
            terminal, _, signal = selection.strip().partition(':')
            connection = one([row for row in connections if row['source'] == board and row['target'] == component
                              and row['target_pin'] == terminal], f'{identity}/{terminal} physical connection')
            pins.append((header_pin(connection['source_pin']), signal))
        if kind == 'gpio':
            requirement['direction'] = runtime['direction']
            mapping['line'] = int(runtime['line'])
            expected = resource['line_pins'].get(str(mapping['line']))
            if len(pins) != 1 or expected is None or pins[0][0] != header_pin(expected):
                raise ValueError(f'{identity}: wiring header and runtime GPIO line disagree')
            mapping['physical_pin'] = expected
        elif kind in ('spi','i2c'):
            if kind == 'spi':
                requirement.update(mode=int(runtime['mode']), device=runtime['dev'],
                                   min_speed_hz=int(interface.get('min_speed_hz') or runtime['max_speed_hz']))
                if product.data['hardware'].get('spi_miso') is False:
                    requirement['requires_miso'] = False
            else:
                requirement.update(device=runtime['dev'],address=int(runtime['address'],0),frequency_hz=int(interface['frequency_hz']))
                mapping['address']=requirement['address']
            signals = {}
            for pin, signal in pins:
                expected = resource['signal_pins'].get(signal)
                if not signal or signal in signals or expected is None or header_pin(expected) != pin:
                    raise ValueError(f'{identity}: SPI wiring must name each signal and match its board pin')
                signals[signal] = expected
            mapping['physical_pins'] = [f'{pin}:{signal}' for signal, pin in signals.items()]
        else:
            if len(pins) != 1 or pins[0][0] not in resource['signal_pins'].values():
                raise ValueError(f'{identity}: physical connector is absent or ambiguous')
            mapping['physical_pin'] = pins[0][0]
            if kind == 'video':
                requirement.update(device=runtime['dev'], min_fps=int(interface.get('min_fps') or runtime['fps']))
        requirements.append(requirement)
        mappings.append(mapping)
    if not requirements:
        raise ValueError('The interface contract must not be empty')
    name = settings['product']
    return ({'schema_version': 1, 'product': name, 'requirements': requirements},
            {'schema_version': 1, 'product': name, 'target_id': capabilities['target_id'], 'mappings': mappings})


def generate(product, capabilities_path, relative='.gar/hardware-contract'):
    path = Path(relative)
    if path.parts[:2] != ('.gar', 'hardware-contract') or '..' in path.parts:
        raise ValueError('Derived hardware contracts must stay under .gar/hardware-contract/')
    output = inside(product.root, relative, exists=False)
    for item in (product.root / path, *(product.root / path).parents):
        if item == product.root:
            break
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError('Derived hardware output cannot follow links')
    capabilities = read_json(capabilities_path)
    requirements, binding = derive(product, capabilities)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.hardware-contract-', dir=output.parent) as directory:
        temporary = Path(directory)
        staging = temporary / 'current'
        staging.mkdir()
        for name, data in (('requirements.json', requirements), ('binding.json', binding)):
            (staging / name).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        if output.exists():
            output.rename(temporary / 'previous')
        staging.rename(output)
    return output
