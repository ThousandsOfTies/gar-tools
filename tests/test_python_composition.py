import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from package import package_product
from product import Product
from python_app import clean, environment, package


class PythonCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = {
            'schema_version': 1, 'id': 'unrelated-product',
            'components': {'application': 'sources/app', 'tools': 'sources/tools', 'board': 'sources/board'},
            'board_profile': 'os',
            'hardware': {'physical': 'hardware', 'simulation': '.gar/hardware/simulation',
                         'simulation_overrides': 'hardware/overrides.csv'},
            'build': {'backend': 'python', 'directory': 'build/python'},
            'launch': {'entrypoint': 'main.py', 'runtime': 'python',
                       'environment': {'COMPOSE_TEST_PORT': '1234', 'COMPOSE_TEST_TEXT': "quote ' and $(literal)"},
                       'hardware_environment': {'COMPOSE_TEST_GPIO': {'table': 'gpio', 'name': 'button', 'field': 'line'},
                                                'COMPOSE_TEST_DEBOUNCE': {'table': 'gpio', 'name': 'button', 'field': 'debounce_us'}}},
            'simulation': {'environment': {'COMPOSE_TEST_PORT': '4321'}},
            'deployment': {'manager': 'gar-target', 'application_id': 'unrelated-app'},
            'payload': [{'component': 'application', 'include': ['*.py', 'requirements.txt']}]
        }
        self.profile = {
            'schema_version': 1, 'board': 'fixture-board', 'os': 'Fixture OS', 'architecture': 'aarch64',
            'runtimes': {'python': '/usr/bin/python3'},
            'startup': {'init': 'systemd', 'manager': 'gar-target', 'application_root': '/opt/gar/apps'},
            'gpio': [{'device': '/dev/gpiochip0', 'lines': [2, 3]}], 'spi': [],
            'i2c': [{'device': '/dev/i2c-1', 'bus': 1}]
        }
        self.save('product.json', self.data)
        self.save('sources/board/board.json', {'schema_version': 1, 'id': 'fixture-board', 'profiles': {'os': 'os.json'}})
        self.save('sources/board/os.json', self.profile)
        (self.root / 'sources/tools').mkdir(parents=True)
        self.save('sources/app/main.py', "import os,json\nprint(json.dumps({k:v for k,v in os.environ.items() if k.startswith('COMPOSE_TEST_')}))\n")
        self.save('sources/app/requirements.txt', '')
        self.save('sources/app/.env', 'PRIVATE_MUST_NOT_BE_PACKAGED')
        self.save('hardware/gpio.csv', 'name,chip,line,direction,debounce_us\nbutton,/dev/gpiochip0,2,input,1000\n')
        self.save('hardware/spi.csv', 'name,bus,chip_select,dev,mode,max_speed_hz\n')
        self.save('hardware/overrides.csv', 'table,name,field,value\ngpio,button,debounce_us,0\n')

    def save(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')

    def test_package_preserves_managed_layout_and_contains_only_selected_sources(self):
        output = package_product(Product(self.root), 'artifacts/target')
        manifest = json.loads((output / 'artifact.json').read_text(encoding='utf-8'))
        self.assertEqual([{'src': 'files/unrelated-app', 'dest': '/opt/gar/apps/unrelated-app'}], manifest['deploy']['app']['files'])
        app = output / 'files/unrelated-app'
        self.assertEqual({'main.py', 'requirements.txt', 'run', 'composition.json', 'unrelated-app.env.example'},
                         {path.name for path in app.iterdir()})
        self.assertNotIn('PRIVATE_MUST_NOT_BE_PACKAGED', (app / 'run').read_text(encoding='utf-8'))
        self.assertFalse(any(path.suffix == '.service' for path in output.rglob('*')))
        self.assertTrue((self.root / 'build/python/composition-build.json').is_file())
        with self.assertRaisesRegex(ValueError, 'already exists'):
            package(Product(self.root), 'artifacts/target')

    @unittest.skipUnless(os.name == 'posix' and Path('/usr/bin/python3').is_file(), 'POSIX launcher contract')
    def test_real_launcher_preserves_runtime_overrides_and_quotes_values(self):
        app = package(Product(self.root), 'artifacts/target') / 'files/unrelated-app'
        result = subprocess.run([str(app / 'run')], cwd='/',
                                env={**os.environ, 'COMPOSE_TEST_PORT': '9999'}, capture_output=True, text=True, check=True)
        values = json.loads(result.stdout)
        self.assertEqual('9999', values['COMPOSE_TEST_PORT'])
        self.assertEqual("quote ' and $(literal)", values['COMPOSE_TEST_TEXT'])
        self.assertEqual('2', values['COMPOSE_TEST_GPIO'])
        self.assertEqual('1000', values['COMPOSE_TEST_DEBOUNCE'])

    def test_simulation_changes_only_declared_fields_and_defaults(self):
        product = Product(self.root).validate()
        canonical = (self.root / 'hardware/gpio.csv').read_bytes()
        self.assertEqual('1000', environment(product)['COMPOSE_TEST_DEBOUNCE'])
        simulated = environment(product, 'simulation')
        self.assertEqual('0', simulated['COMPOSE_TEST_DEBOUNCE'])
        self.assertEqual('4321', simulated['COMPOSE_TEST_PORT'])
        self.assertEqual(canonical, (self.root / 'hardware/gpio.csv').read_bytes())

    def test_bad_python_or_escape_cannot_produce_a_target_package(self):
        self.save('sources/app/main.py', 'this is not Python !!!')
        with self.assertRaises(SyntaxError):
            package(Product(self.root), 'artifacts/bad')
        self.assertFalse((self.root / 'artifacts/bad').exists())
        self.save('sources/app/main.py', 'pass\n')
        with self.assertRaisesRegex(ValueError, 'generated child'):
            package(Product(self.root), 'sources/app')
        self.data['payload'][0]['include'] = ['../outside.py']
        self.save('product.json', self.data)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            Product(self.root).validate()

    def test_planned_product_can_describe_resources_but_cannot_build_or_package(self):
        self.data.update(status='planned')
        self.data['build'].update(backend='planned', reason='Physical implementation is not available')
        self.save('product.json', self.data)
        self.assertEqual('planned', Product(self.root).describe()['status'])
        with self.assertRaisesRegex(ValueError, 'planned'):
            Product(self.root).build()
        with self.assertRaisesRegex(ValueError, 'planned'):
            package(Product(self.root), 'artifacts/planned')
        self.assertFalse((self.root / 'artifacts').exists())

    def test_i2c_binding_is_checked_against_the_selected_board(self):
        self.save('hardware/i2c.csv', 'name,bus,dev,address\nsensor,1,/dev/i2c-1,0x29\n')
        Product(self.root).validate()
        self.save('hardware/i2c.csv', 'name,bus,dev,address\nsensor,1,/dev/i2c-1,0xff\n')
        with self.assertRaisesRegex(ValueError, 'I2C'):
            Product(self.root).validate()
        self.save('hardware/i2c.csv', 'name,bus,dev,address\nsensor,1,/dev/i2c-1,0x29\nother,1,/dev/i2c-1,0x29\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate I2C'):
            Product(self.root).validate()

    def test_replacement_and_clean_touch_only_generated_staging(self):
        output = package(Product(self.root), 'artifacts/staging')
        (output / 'stale-private-file').write_text('previous staging', encoding='utf-8')
        package(Product(self.root), 'artifacts/staging', replace=True)
        self.assertFalse((output / 'stale-private-file').exists())
        clean(Product(self.root), 'artifacts/staging')
        self.assertFalse(output.exists())
        self.assertTrue((self.root / 'sources/app/main.py').is_file())
        with self.assertRaisesRegex(ValueError, 'generated child'):
            clean(Product(self.root), 'sources/app')

    @unittest.skipUnless(os.name == 'posix', 'POSIX symlink fixture')
    def test_generated_path_link_cannot_redirect_cleanup_to_application_sources(self):
        (self.root / 'artifacts').mkdir()
        (self.root / 'artifacts/linked').symlink_to(self.root / 'sources/app', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'link'):
            clean(Product(self.root), 'artifacts/linked')
        with self.assertRaisesRegex(ValueError, 'link'):
            package(Product(self.root), 'artifacts/linked/output', replace=True)
        self.assertTrue((self.root / 'sources/app/main.py').is_file())


if __name__ == '__main__':
    unittest.main()
