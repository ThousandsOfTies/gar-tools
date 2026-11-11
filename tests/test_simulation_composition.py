import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from artifact import run
from product import Product
import test_python_composition as fixtures


class SimulationPackageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PythonCompositionTests('test_simulation_changes_only_declared_fields_and_defaults')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.data['simulation']['packaging'] = {
            'panel': 'panel', 'after': ['network-online.target', 'gar-bridge.service'],
            'wants': ['gar-bridge.service'], 'environment_files': ['/etc/gar/system/unrelated-app.env']}
        self.fixture.save('panel/index.html', '<gar-display></gar-display>')
        self.fixture.save('product.json', self.fixture.data)

    def test_simulator_preserves_app_bytes_and_resolves_only_simulation_hardware(self):
        product = Product(self.fixture.root).validate()
        source = self.fixture.root / 'sources/app/main.py'
        before = source.read_bytes()
        output = run(product, 'sim_app')
        manifest = json.loads((output / 'artifact.json').read_text())
        self.assertEqual('linux-device', manifest['target'])
        self.assertEqual('sim_app', manifest['artifact_kind'])
        self.assertEqual(before, (output / 'files/unrelated-app/main.py').read_bytes())
        unit = (output / 'files/gar-sim-app.service').read_text()
        self.assertIn('COMPOSE_TEST_PORT=4321', unit)
        self.assertIn('COMPOSE_TEST_DEBOUNCE=0', unit)
        self.assertIn('ExecStart=/usr/bin/python3 /usr/local/lib/gar/apps/unrelated-app/main.py', unit)
        self.assertLess(unit.index('Environment='), unit.index('EnvironmentFile='))
        self.assertNotIn('PRIVATE_MUST_NOT_BE_PACKAGED', unit)
        self.assertEqual(before, source.read_bytes())
        run(product, 'sim_app', clean=True)
        self.assertFalse(output.exists())
        self.assertTrue(source.exists())

    def test_service_injection_and_cross_product_replacement_are_rejected(self):
        self.fixture.data['simulation']['packaging']['after'] = ['valid.service\nExecStart=bad']
        self.fixture.save('product.json', self.fixture.data)
        with self.assertRaisesRegex(ValueError, 'dependency unit'):
            run(Product(self.fixture.root).validate(), 'sim_app')
        self.fixture.data['simulation']['packaging']['after'] = ['gar-bridge.service']
        self.fixture.save('product.json', self.fixture.data)
        output = self.fixture.root / 'artifacts/from-codespace'
        output.mkdir(parents=True)
        (output / 'artifact.json').write_text(json.dumps({'name': 'other-product', 'target': 'linux-device'}))
        with self.assertRaisesRegex(ValueError, 'another Product'):
            run(Product(self.fixture.root).validate(), 'sim_app')
        self.assertTrue((output / 'artifact.json').exists())


if __name__ == '__main__':
    unittest.main()
