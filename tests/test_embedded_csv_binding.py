import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'composition'))
from product import Product
import test_embedded_composition as fixtures


class EmbeddedCsvTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EmbeddedCompositionTests('test_native_build_cannot_be_confused_with_firmware')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.data['hardware'].update(binding='.gar/composition/binding.json', binding_csv={
            'components':'hardware/components.csv','connections':'hardware/connections.csv','board_component':'board'})
        self.fixture.save('hardware/components.csv','component_id,name,kind,part_number,description\n'
                          'board,Board,board,Fixture,Board resources\n'
                          'screen,Display,display,builtin:screen,Internal display\n'
                          'ok,Button,input,builtin:ok,Internal button\n')
        self.fixture.save('hardware/connections.csv','source,source_pin,target,target_pin,signal,description\n'
                          'board,screen,screen,pixels,display,Internal selected display\n'
                          'board,ok,ok,input,button,Internal selected button\n')
        self.fixture.save('product.json',self.fixture.data)

    def test_read_only_validation_and_generated_legacy_binding_use_only_csv(self):
        legacy = self.fixture.root / 'hardware/binding.json'
        if legacy.exists():
            legacy.unlink()
        product = Product(self.fixture.root).validate()
        self.assertEqual({'schema_version':1,'display':'screen','buttons':['ok'],'orientation':'portrait'},product.binding)
        output = self.fixture.root / '.gar/composition/binding.json'
        self.assertFalse(output.exists(),'offline validation must not generate or rewrite inputs')
        product.prepare()
        self.assertEqual(product.binding,json.loads(output.read_text()))
        self.assertFalse(legacy.exists())

    def test_unknown_or_duplicated_builtin_resource_cannot_be_silently_selected(self):
        path = self.fixture.root / 'hardware/connections.csv'
        original = path.read_text()
        path.write_text(original.replace('board,ok,ok,input,button','board,unknown,ok,input,button'))
        with self.assertRaisesRegex(ValueError,'Button CSV resource'):
            Product(self.fixture.root).validate()
        path.write_text(original+'board,ok,ok,input,button,Duplicate\n')
        with self.assertRaisesRegex(ValueError,'selected twice'):
            Product(self.fixture.root).validate()


if __name__ == '__main__':
    unittest.main()
