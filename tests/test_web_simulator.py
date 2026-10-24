from __future__ import annotations
import functools
import http.client
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('web_simulator', ROOT / 'web-simulator/serve.py')
SIM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SIM)


class WebSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.panel = self.root / 'panel'
        self.panel.mkdir()
        (self.panel / 'index.html').write_text('<h1>Test panel</h1>', encoding='utf-8')
        (self.panel / 'app.mjs').write_text('export const value = 1;', encoding='utf-8')
        (self.panel / 'ui.wasm').write_bytes(b'\x00asm\x01\x00\x00\x00')
        (self.panel / '.env.local').write_text('PRIVATE_TOKEN=hidden', encoding='utf-8')
        (self.root / 'outside.json').write_text('{"private":true}', encoding='utf-8')
        self.server = SIM.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(SIM.PanelHandler, panel=self.panel))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def request(self, path):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()

    def test_panel_and_shared_modules_use_separate_roots(self):
        self.assertEqual(200, self.request('/')[0])
        status, mime, body = self.request('/components/twatch-2020.mjs')
        self.assertEqual(200, status)
        self.assertIn('javascript', mime)
        self.assertIn(b'gar-twatch-2020', body)
        self.assertEqual(200, self.request('/healthz')[0])

    def test_wasm_uses_streaming_compilation_mime_type(self):
        status, mime, body = self.request('/ui.wasm')
        self.assertEqual(200, status)
        self.assertEqual('application/wasm', mime)
        self.assertTrue(body.startswith(b'\x00asm'))

    def test_common_components_and_product_components_coexist(self):
        (self.panel / 'components').mkdir()
        (self.panel / 'components/product.mjs').write_text('export const product = true;')
        for path in ['/gar-components/controls.mjs', '/gar-components/event-log.mjs',
                     '/gar-components/display.mjs', '/components/product.mjs']:
            with self.subTest(path=path):
                self.assertEqual(200, self.request(path)[0])
        output = self.root / 'export'
        SIM.export_panel(self.panel, output)
        self.assertTrue((output / 'gar-components/display.mjs').is_file())
        self.assertTrue((output / 'components/product.mjs').is_file())

    def test_product_cannot_shadow_common_assets_on_export(self):
        (self.panel / 'gar-components').mkdir()
        (self.panel / 'gar-components/display.mjs').write_text('unexpected override')
        output = self.root / 'export'
        with self.assertRaises(ValueError):
            SIM.export_panel(self.panel, output)
        self.assertFalse(output.exists())

    def test_hidden_files_traversal_and_directory_listing_are_not_served(self):
        for path in ['/.env.local', '/%2e%2e/outside.json', '/components/../serve.py', '/components/',
                     '/gar-components/../serve.py', '/gar-components/', '/C:/outside.json']:
            with self.subTest(path=path):
                self.assertEqual(404, self.request(path)[0])

    def test_static_export_is_complete_without_credentials(self):
        output = self.root / 'output'
        SIM.export_panel(self.panel, output)
        self.assertTrue((output / 'index.html').is_file())
        self.assertTrue((output / 'components/twatch-2020.mjs').is_file())
        self.assertTrue((output / 'components/lvgl-surface.mjs').is_file())
        self.assertEqual((self.panel / 'ui.wasm').read_bytes(), (output / 'ui.wasm').read_bytes())
        self.assertFalse((output / '.env.local').exists())
        with self.assertRaises(ValueError):
            SIM.export_panel(self.panel, output)
        with self.assertRaises(ValueError):
            SIM.export_panel(self.panel, self.panel / 'output')

    def test_symlink_cannot_escape_public_root(self):
        try:
            (self.panel / 'leak.json').symlink_to(self.root / 'outside.json')
        except OSError:
            self.skipTest('Creating symlinks is unavailable on this host')
        self.assertEqual(404, self.request('/leak.json')[0])


if __name__ == '__main__':
    unittest.main()
