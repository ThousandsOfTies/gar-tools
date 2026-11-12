"""Run declared SDK packaging steps in the selected builder, never a Sim Host.

SDK-specific closure/pinmux/image composition stays in the Product adapter.
The shared entry point handles argument validation and environment handoff.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from product import inside


def command(root, values):
    if not isinstance(values, list) or not values or not all(isinstance(v, str) and v and '\0' not in v for v in values):
        raise ValueError('Recipe command must be a nonempty string array')
    values = [value.replace('{root}', str(root)) for value in values]
    # Python comes from the selected builder, including its virtual environment.
    if values[0] == 'python3':
        values[0] = sys.executable
    return values


def run(root, data, kind, *, clean=False):
    root = Path(root).resolve()
    settings = data['build']['recipes'][kind]
    commands = settings.get('clean_commands' if clean else 'commands')
    if not isinstance(commands, list) or not commands:
        raise ValueError('Recipe does not declare this build/clean operation')
    commands = [command(root, values) for values in commands]
    target = json.loads((inside(root, data['components']['board']) / 'board.json').read_text(encoding='utf-8-sig'))
    expected = target.get('target_id', target['id'])
    if os.environ.get('GAR_TARGET', expected) != expected and kind == 'target_app':
        raise ValueError('Product has fixed target ' + expected)
    environment = os.environ.copy()
    declared = settings.get('environment', {})
    if not isinstance(declared, dict) or not all(re.fullmatch(r'[A-Z_][A-Z0-9_]*', key) and isinstance(value, str) for key, value in declared.items()):
        raise ValueError('Invalid recipe environment')
    environment.update({key: value.replace('{root}', str(root)) for key, value in declared.items()})
    # Clean never needs a generated binding or the SDK. Providers validate their
    # own Product/board contract before packaging and return JSON, not shell code.
    provider = settings.get('environment_command')
    if provider:
        result = subprocess.run(command(root, provider) + (['--clean'] if clean else []), cwd=root,
                                env=environment, text=True, capture_output=True, check=True)
        values = json.loads(result.stdout)
        if not isinstance(values, dict) or not all(re.fullmatch(r'[A-Z_][A-Z0-9_]*', key) and isinstance(value, str) and '\0' not in value for key, value in values.items()):
            raise ValueError('Recipe environment provider must return string assignments')
        environment.update(values)
    for values in commands:
        subprocess.run(values, cwd=root, env=environment, check=True)
    return root / 'artifacts/from-codespace'
