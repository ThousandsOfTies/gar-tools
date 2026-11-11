"""Build a declared native simulation archive in the selected Linux builder.

This retains the App and OS device-driver paths. It does not run a VM, copy
credentials, deploy services, or choose Product behavior.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from product import inside
from python_app import generated_output

IGNORED = shutil.ignore_patterns('.git', '.gar', '__pycache__', '*.pyc', 'node_modules', 'build', 'artifacts')


def package(product):
    settings = product.data['simulation']['native_artifact']
    output = generated_output(product, 'artifacts/from-codespace')
    if output.exists():
        previous = json.loads((output / 'artifact.json').read_text(encoding='utf-8'))
        if previous.get('composition', {}).get('product') != product.id:
            raise ValueError('Refusing to replace unowned native simulation staging')
    arch = os.environ.get('GAR_SIM_ARCH')
    if arch not in ('x86_64', 'aarch64', 'armv7l'):
        raise ValueError('GAR_SIM_ARCH must identify the declared Linux simulation host')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.native-simulation-', dir=output.parent) as directory:
        temporary = Path(directory)
        work = temporary / 'source'
        work.mkdir()
        for relative in settings['sources']:
            source = inside(product.root, relative)
            destination = inside(work, relative, exists=False)
            if source.is_symlink() or source.is_dir() and any(path.is_symlink() for path in source.rglob('*')):
                raise ValueError('Native simulation source cannot contain links')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, ignore=IGNORED)
            else:
                shutil.copyfile(source, destination)
        build = work / 'build'
        build.mkdir()
        tools = inside(work, product.data['components']['tools'])
        environment = {**os.environ, **product.data['build'].get('environment', {}),
                       'GAR_TOOLS_ROOT': str(tools), 'GAR_BUILD_DIR': str(build)}
        for command in settings['commands']:
            if not isinstance(command, list) or not command or not all(isinstance(value, str) for value in command):
                raise ValueError('Simulation build commands must be nonempty argument arrays')
            arguments = [value.replace('{build}', str(build)).replace('{root}', str(work)) for value in command]
            subprocess.run(arguments, cwd=work, env=environment, check=True)
        for name in settings['outputs']:
            binary = inside(build, name)
            header = binary.read_bytes()[:20]
            machine = {'x86_64': 62, 'aarch64': 183, 'armv7l': 40}[arch]
            if len(header) < 20 or header[:4] != b'\x7fELF' or int.from_bytes(header[18:20], 'little') != machine:
                raise ValueError(f'Native simulation output has wrong architecture: {name}')
        checks = {path.relative_to(work).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(work.rglob('*')) if path.is_file()}
        (work / 'simulator-manifest.json').write_text(json.dumps(checks, sort_keys=True) + '\n', encoding='utf-8')
        bundle = temporary / 'bundle'
        (bundle / 'files').mkdir(parents=True)

        def archive_mode(info):
            if info.issym() or info.islnk():
                raise ValueError('Simulation archive cannot contain links')
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mode = 0o755 if info.isdir() or info.name.startswith('build/') else 0o644
            return info

        with tarfile.open(bundle / 'files/vm.tar.gz', 'w:gz') as archive:
            for item in sorted(work.iterdir()):
                archive.add(item, arcname=item.name, filter=archive_mode)
        entry = settings['entrypoint']
        inside(work, entry)
        manifest = {'name': product.id + '-simulation', 'target': 'linux-device', 'entrypoint': entry,
                    'composition': product.describe(), 'artifact_kind': 'sim_app',
                    'simulation_architecture': arch,
                    'deploy': {'app': {'files': [{'src': 'files/vm.tar.gz', 'dest': 'vm.tar.gz'}]}}}
        (bundle / 'artifact.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        if output.exists():
            output.rename(temporary / 'previous')
        bundle.rename(output)
    return output
