"""Build and atomically stage a board-qualified native Product artifact."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from python_app import generated_output


def owned_output(product):
    output = generated_output(product, 'artifacts/from-codespace')
    if output.exists():
        manifest = json.loads((output / 'artifact.json').read_text(encoding='utf-8'))
        target = product.data.get('deployment', {}).get('artifact_target', product.board['id'])
        if manifest.get('composition', {}).get('product') != product.id or manifest.get('target') != target:
            raise ValueError('Refusing to replace another Product/target staging directory')
    return output


def run(product, *, clean=False):
    output = owned_output(product)
    if clean:
        from python_app import clean as clean_staging
        clean_staging(product, 'artifacts/from-codespace')
        return output
    product.build()
    from package import package_product
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.native-target-', dir=output.parent) as directory:
        temporary = Path(directory)
        bundle = temporary / 'bundle'
        package_product(product, str(bundle.relative_to(product.root)))
        if output.exists():
            output.rename(temporary / 'previous')
        bundle.rename(output)
    return output
