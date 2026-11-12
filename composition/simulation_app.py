"""Package unchanged Python App code for GAR's Linux virtual devices, offline."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import tempfile

from product import inside
from python_app import build, environment, generated_output, payload_files, launch_script


def owned_output(product):
    output = generated_output(product, 'artifacts/from-codespace')
    if output.exists():
        manifest = json.loads((output / 'artifact.json').read_text(encoding='utf-8'))
        app = product.data['deployment']['application_id']
        names = {product.id, app + '-target', app + '-simulation'}
        if manifest.get('composition', {}).get('product') != product.id and manifest.get('name') not in names:
            raise ValueError('Refusing to replace another Product staging directory')
    return output


def settings(product):
    if product.data['build'].get('backend') != 'python':
        raise ValueError('The interpreted simulator packager requires the Python backend')
    packaging = product.data['simulation']['packaging']
    for key in ('after', 'wants'):
        for unit in packaging.get(key, []):
            if not re.fullmatch(r'[A-Za-z0-9_@.:-]+\.(?:service|target)', unit):
                raise ValueError('Invalid simulation dependency unit')
    for filename in packaging.get('environment_files', []):
        if not re.fullmatch(r'/etc/gar/[A-Za-z0-9_./-]+\.env', filename) or '..' in Path(filename).parts:
            raise ValueError('Simulation environment files must stay under /etc/gar/')
    panel = inside(product.root, packaging['panel'])
    if not panel.is_dir() or panel.is_symlink() or any(path.is_symlink() for path in panel.rglob('*')):
        raise ValueError('Simulation panel must be a regular directory without links')
    return packaging, product.data['deployment']['application_id'], panel


def service(product):
    packaging, app, _ = settings(product)
    destination = '/usr/local/lib/gar/apps/' + app
    lines = ['[Unit]', 'Description=' + app + ' simulation application']
    for key in ('after', 'wants'):
        if packaging.get(key):
            lines.append(key.title() + '=' + ' '.join(packaging[key]))
    lines += ['PartOf=gar-sim.target', '', '[Service]', 'Type=simple', 'WorkingDirectory=' + destination]
    values = environment(product, 'simulation')
    if product.data['launch'].get('hardware_environment_csv'):
        from runtime_csv import references
        inherited = product.data['simulation'].get('environment', {})
        values = {key:value for key,value in values.items() if key not in references(product) or key in inherited}
    for key, value in values.items():
        lines.append('Environment=' + json.dumps((key + '=' + value).replace('%', '%%')))
    # Topology overrides follow static defaults, matching GAR system deploy.
    for filename in packaging.get('environment_files', []):
        lines.append('EnvironmentFile=-' + filename)
    if packaging.get('wait_for_hardware_socket', True):
        lines.append("ExecStartPre=/bin/sh -c 'for n in $(seq 1 50); do [ -S /run/gar/hw_sim.sock ] && exit 0; sleep 0.1; done; exit 1'")
    entry = product.data['launch']['entrypoint']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.py', entry):
        raise ValueError('Simulation entrypoint must be a selected Python filename')
    interpreter = product.profile['runtimes'][product.data['launch']['runtime']]
    command = '/bin/sh ' + destination + '/run' if product.data['launch'].get('hardware_environment_csv') else interpreter + ' ' + destination + '/' + entry
    lines += ['ExecStart=' + command, 'Restart=on-failure', 'RestartSec=3', '']
    return '\n'.join(lines)


def package(product):
    _, app, panel = settings(product)
    unit = service(product)
    build(product)  # Syntax validation; never imports application/device code.
    output = owned_output(product)
    description = product.describe()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.simulation-package-', dir=output.parent) as folder:
        temporary = Path(folder)
        bundle = temporary / 'bundle'
        files = bundle / 'files'
        application = files / app
        application.mkdir(parents=True)
        for relative, source in payload_files(product).items():
            destination = application / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        from runtime_csv import install
        install(product, application)
        if product.data['launch'].get('hardware_environment_csv'):
            (application / 'run').write_text(launch_script(product), encoding='utf-8', newline='\n')
        shutil.copytree(panel, files / 'panel', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
        panel_destination = '/usr/local/share/gar/panels/' + app
        (files / 'panel-dir').write_text(panel_destination + '\n', encoding='utf-8')
        (files / 'gar-sim-app.service').write_text(unit, encoding='utf-8', newline='\n')
        manifest = {'name': app + '-simulation', 'target': 'linux-device', 'composition': description,
            'artifact_kind': 'sim_app', 'deploy': {'app': {'files': [
                {'src': 'files/' + app, 'dest': '/usr/local/lib/gar/apps/' + app},
                {'src': 'files/panel', 'dest': panel_destination},
                {'src': 'files/panel-dir', 'dest': '/etc/gar/panel-dir', 'mode': '0644'},
                {'src': 'files/gar-sim-app.service', 'dest': '/etc/systemd/system/gar-sim-app.service', 'mode': '0644'}]}}}
        (bundle / 'artifact.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            output.rename(temporary / 'previous')
        bundle.rename(output)
    return output
