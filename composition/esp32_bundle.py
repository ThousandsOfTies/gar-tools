"""Export a composition's PlatformIO output for GAR's ESP32 deploy adapter."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile

from embedded import runtime_paths
from python_app import generated_output


def export(product, build_dir):
    chip = product.profile['flash']['chip']
    chip_ids = {'esp32': 0, 'esp32s3': 9}
    if chip not in chip_ids:
        raise ValueError('Unsupported ESP32 chip')
    flash_size = product.profile['flash']['size_bytes']
    _, _, cache, _ = runtime_paths(product.root, product.profile['platformio']['core_version'])
    source = Path(build_dir)
    payload = {name: (source / name).read_bytes()
               for name in ('bootloader.bin', 'partitions.bin', 'firmware.bin')}
    payload['boot_app0.bin'] = (cache / 'core/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin').read_bytes()
    for name in ('bootloader.bin', 'firmware.bin'):
        data = payload[name]
        if len(data) < 24 or data[0] != 0xe9 or int.from_bytes(data[12:14], 'little') != chip_ids[chip]:
            raise ValueError(f'{name}: wrong ESP32 image chip')
    boot_offset = 0 if chip == 'esp32s3' else 0x1000
    if not 0 < len(payload['bootloader.bin']) <= 0x8000 - boot_offset:
        raise ValueError('Bootloader overlaps partition table')
    if not 0 < len(payload['partitions.bin']) <= 0x1000 or len(payload['boot_app0.bin']) != 8192:
        raise ValueError('Invalid partition/boot selection image size')
    table = payload['partitions.bin']
    ranges, app_size, digest_seen = [], None, False
    for offset in range(0, len(table), 32):
        entry = table[offset:offset + 32]
        if entry == b'\xff' * 32:
            break
        if entry[:2] == b'\xeb\xeb':
            if entry[2:16] != b'\xff' * 14 or entry[16:] != hashlib.md5(table[:offset]).digest():
                raise ValueError('Partition table checksum mismatch')
            if any(value != 255 for value in table[offset + 32:]):
                raise ValueError('Data after partition checksum')
            digest_seen = True
            break
        if len(entry) != 32 or entry[:2] != b'\xaa\x50':
            raise ValueError('Invalid partition entry')
        kind, _, start, size = struct.unpack_from('<BBII', entry, 2)
        if start < 0x9000 or not size or start + size > flash_size:
            raise ValueError('Partition outside flash')
        if any(start < high and start + size > low for low, high in ranges):
            raise ValueError('Overlapping partitions')
        ranges.append((start, start + size))
        if kind == 0 and start == 0x10000:
            app_size = size
    if not digest_seen or app_size is None or len(payload['firmware.bin']) > app_size:
        raise ValueError('Firmware does not fit a verified app partition')
    payload['flash.json'] = (json.dumps({'schema_version': 1, 'chip': chip}) + '\n').encode()
    output = generated_output(product, 'artifacts/from-codespace')
    if output.exists():
        previous = json.loads((output / 'artifact.json').read_text(encoding='utf-8'))
        if previous.get('name') != product.data['id'] or previous.get('target') != 'esp32':
            raise ValueError('Refusing to replace another Product firmware staging directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.esp32-export-', dir=output.parent) as temporary:
        bundle = Path(temporary) / 'bundle'
        firmware = bundle / 'files/firmware'
        firmware.mkdir(parents=True)
        for name, data in payload.items():
            (firmware / name).write_bytes(data)
        (firmware / 'SHA256SUMS').write_text(''.join(
            f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data in payload.items()), encoding='utf-8')
        manifest = {'name': product.data['id'], 'target': 'esp32',
                    'deploy': {'app': {'files': [{'src': 'files/firmware', 'dest': 'firmware'}]}}}
        (bundle / 'artifact.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            output.rename(Path(temporary) / 'previous')
        bundle.rename(output)
    return output
