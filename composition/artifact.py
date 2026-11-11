"""Build/package through a Product declaration; never deploy or open devices."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from product import inside

HOOKS = {'target_app': 'target_hook', 'sim_app': 'simulation_hook', 'sim_runtime': 'runtime_hook'}


def run(product, kind, *, clean=False):
    if kind not in HOOKS:
        raise ValueError(f'Unknown artifact kind: {kind}')
    settings = product.data['build']
    if kind == 'sim_app' and product.data.get('simulation', {}).get('native_artifact'):
        if clean:
            raise ValueError('Native simulation cleanup is not declared; existing snapshots are retained')
        from native_simulation import package
        return package(product)
    if kind == 'sim_app' and settings.get('backend') == 'python' and product.data.get('simulation', {}).get('packaging'):
        from simulation_app import owned_output, package
        if clean:
            output = owned_output(product)
            if output.exists():
                manifest = json.loads((output / 'artifact.json').read_text(encoding='utf-8'))
                if manifest.get('target') != 'linux-device' or manifest.get('artifact_kind') != 'sim_app':
                    raise ValueError('Staging is not a declared simulation App; refusing cleanup')
            from python_app import clean as clean_staging
            clean_staging(product, 'artifacts/from-codespace')
            return output
        return package(product)
    hook = settings.get(HOOKS[kind])
    if hook:
        path = inside(product.root, hook)
        command = [sys.executable, str(path)] if path.suffix == '.py' else ['bash', str(path)]
        subprocess.run([*command, *(['clean'] if clean else [])], cwd=product.root, env=os.environ.copy(), check=True)
        return product.root / 'artifacts/from-codespace'
    if kind != 'target_app':
        raise ValueError(f'{kind}: no simulation packager declared; refusing to substitute a target build')
    backend = settings.get('backend')
    if product.kind != 'platformio' and backend not in ('python', 'planned'):
        raise ValueError('This native backend needs an explicit target artifact adapter')
    if clean:
        output = product.root / 'artifacts/from-codespace'
        if output.exists():
            manifest = json.loads((output / 'artifact.json').read_text(encoding='utf-8'))
            identity = manifest.get('composition', {}).get('product')
            names = {product.id, product.data.get('deployment', {}).get('application_id', '') + '-target'}
            if identity != product.id and manifest.get('name') not in names:
                raise ValueError('Staging belongs to another Product; refusing cleanup')
            expected_target = 'esp32' if product.kind == 'platformio' else product.board['id']
            if manifest.get('target') != expected_target:
                raise ValueError('Staging belongs to another artifact target; refusing cleanup')
        from python_app import clean as clean_staging
        clean_staging(product, 'artifacts/from-codespace')
        return output
    if product.kind == 'platformio':
        from embedded import build
        from esp32_bundle import export
        return export(product, build(product))
    from python_app import package
    return package(product, 'artifacts/from-codespace', replace=True)
