"""Package interpreted Linux applications from declarative Product inputs."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import shutil
import tempfile
from pathlib import Path

from product import inside


def payload_files(product):
    files = {}
    for selection in product.data['payload']:
        source = product.components[selection['component']]
        destination = selection.get('destination', '')
        if destination and (Path(destination).is_absolute() or '..' in Path(destination).parts):
            raise ValueError('Payload destination must stay inside the application')
        for pattern in selection['include']:
            if Path(pattern).is_absolute() or '..' in Path(pattern).parts:
                raise ValueError('Payload source pattern escapes its component')
            matches = sorted(source.glob(pattern))
            if not matches:
                raise ValueError(f'Payload source is missing: {pattern}')
            for match in matches:
                if match.is_symlink() or (hasattr(match, 'is_junction') and match.is_junction()):
                    raise ValueError('Payload source cannot be a link')
                path = inside(source, match.relative_to(source).as_posix())
                if not path.is_file():
                    raise ValueError('Select individual payload files, not directories')
                relative = (Path(destination) / path.name).as_posix()
                if relative in files:
                    raise ValueError(f'Duplicate payload destination: {relative}')
                if relative in ('run', 'composition.json', product.data['deployment']['application_id'] + '.env.example'):
                    raise ValueError('Payload shadows a generated composition file')
                files[relative] = path
    return files


def environment(product, environment='physical'):
    settings = product.data['launch']
    result = {key: str(value) for key, value in settings.get('environment', {}).items()}
    tables = {'gpio': product.gpio, 'spi': product.spi, 'i2c': product.i2c}
    if environment == 'simulation':
        from product import csv_rows
        directory = product.hardware_for(environment)
        tables['gpio'] = csv_rows(directory / 'gpio.csv')
        tables['spi'] = csv_rows(directory / 'spi.csv')
        result.update({key: str(value) for key, value in product.data['simulation']['environment'].items()})
    elif environment != 'physical':
        raise ValueError(f'Unknown environment: {environment}')
    for key, reference in settings.get('hardware_environment', {}).items():
        rows = [row for row in tables[reference['table']] if row['name'] == reference['name']]
        if len(rows) != 1 or reference['field'] not in rows[0] or rows[0][reference['field']] == '':
            raise ValueError(f'Missing or ambiguous hardware environment: {key}')
        result[key] = rows[0][reference['field']]
    for key, value in result.items():
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or any(char in value for char in '\0\r\n'):
            raise ValueError('Invalid launch environment')
    return result


def validate(product):
    data = product.data
    deployment = data['deployment']
    if data['build']['backend'] not in ('python', 'planned'):
        raise ValueError('Unsupported declared application backend')
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', deployment['application_id']):
        raise ValueError('Invalid managed application id')
    if deployment['manager'] != 'gar-target' or product.profile['startup'].get('manager') != 'gar-target':
        raise ValueError('Application and board startup managers must match')
    root = product.profile['startup']['application_root']
    if root != '/opt/gar/apps':
        raise ValueError('GAR-managed applications require the standard application root')
    output = Path(data['build']['directory'])
    if len(output.parts) < 2 or output.parts[0] not in ('build', '.gar', 'artifacts'):
        raise ValueError('Build output must be in a generated directory')
    inside(product.root, data['build']['directory'], exists=False)
    files = payload_files(product)
    if data['build']['backend'] == 'planned':
        if data.get('status') != 'planned' or not data['build'].get('reason'):
            raise ValueError('Planned builds must declare their status and reason')
        return product
    entry = data['launch']['entrypoint']
    if entry not in files or not entry.endswith('.py'):
        raise ValueError('The Python entrypoint must be in the selected payload')
    runtime = product.profile['runtimes'][data['launch']['runtime']]
    if not re.fullmatch(r'/usr/bin/[A-Za-z0-9_.-]+', runtime):
        raise ValueError('Runtime must be a system interpreter')
    environment(product)
    return product


def build(product):
    validate(product)
    if product.data['build']['backend'] == 'planned':
        raise ValueError('Physical target is planned: ' + product.data['build']['reason'])
    files = payload_files(product)
    hashes = {}
    for relative, source in files.items():
        if source.suffix == '.py':
            ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
        hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
    output = inside(product.root, product.data['build']['directory'], exists=False)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'composition-build.json').write_text(json.dumps({
        'mode': 'interpreted', 'board': product.board['id'], 'profile': product.data['board_profile'],
        'files': hashes,
    }, indent=2) + '\n', encoding='utf-8')
    return output


def launch_script(product):
    settings = product.data['launch']
    values = environment(product)
    lines = ['#!/bin/sh', 'set -eu', 'cd -- "$(dirname -- "$0")"']
    for key, value in values.items():
        lines += [f'if [ -z "${{{key}:-}}" ]; then {key}={shlex.quote(value)}; fi', f'export {key}']
    runtime = product.profile['runtimes'][settings['runtime']]
    lines.append(f'exec {shlex.quote(runtime)} {shlex.quote(settings["entrypoint"])} "$@"')
    return '\n'.join(lines) + '\n'


def generated_output(product, relative):
    path = Path(relative)
    if len(path.parts) < 2 or path.parts[0] != 'artifacts':
        raise ValueError('Package output must be a generated child of artifacts/')
    unresolved = product.root / path
    for candidate in (unresolved, *unresolved.parents):
        if candidate == product.root:
            break
        if candidate.is_symlink() or (hasattr(candidate, 'is_junction') and candidate.is_junction()):
            raise ValueError('Package output cannot contain a link')
    output = inside(product.root, relative, exists=False)
    if not output.is_relative_to(product.root / 'artifacts'):
        raise ValueError('Resolved package output escapes artifacts/')
    return output


def clean(product, relative):
    output = generated_output(product, relative)
    if output.exists():
        # Only this validated workspace-local staging path is moved/cleaned.
        with tempfile.TemporaryDirectory(prefix='.composition-clean-', dir=output.parent) as folder:
            output.rename(Path(folder) / 'previous')


def package(product, relative, *, replace=False):
    build(product)
    output = generated_output(product, relative)
    if output.exists() and not replace:
        raise ValueError(f'Package already exists: {output}')
    app_id = product.data['deployment']['application_id']
    destination = product.profile['startup']['application_root'] + '/' + app_id
    source_directory = 'files/' + app_id
    description = product.describe()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.composition-package-', dir=output.parent) as folder:
        temporary = Path(folder)
        bundle = temporary / 'bundle'
        app = bundle / source_directory
        app.mkdir(parents=True)
        for relative_file, source in payload_files(product).items():
            target = app / relative_file
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        (app / 'run').write_text(launch_script(product), encoding='utf-8', newline='\n')
        (app / 'run').chmod(0o755)
        example = '# Optional runtime overrides; generated from Product defaults.\n'
        example += '\n'.join(key + '=' + json.dumps(value) for key, value in environment(product).items()) + '\n'
        (app / (app_id + '.env.example')).write_text(example, encoding='utf-8', newline='\n')
        (app / 'composition.json').write_text(json.dumps(description, indent=2) + '\n', encoding='utf-8')
        manifest = {'name': app_id + '-target', 'target': product.board['id'], 'composition': description,
                    'deploy': {'app': {'files': [{'src': source_directory, 'dest': destination}]}}}
        (bundle / 'artifact.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            output.rename(temporary / 'previous')
        bundle.rename(output)
    return output
