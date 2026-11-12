import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'composition'))
from recipe import run
from native_target import run as native


class RecipeTests(unittest.TestCase):
    def fixture(self,root):
        board=root/'board';board.mkdir()
        (board/'board.json').write_text(json.dumps({'id':'fixture-board'}))
        (root/'environment.py').write_text("import json,sys\nprint(json.dumps({'RECIPE_LITERAL':'literal $(echo no) '+str('--clean' in sys.argv)}))\n")
        (root/'package.py').write_text("import json,os,sys\nfrom pathlib import Path\nPath('called.json').write_text(json.dumps([sys.argv[1:],os.environ['RECIPE_LITERAL'],os.environ['SDK_OVERRIDE']]))\n")
        recipe={'commands':[['python3','package.py','build']],
                'clean_commands':[['python3','package.py','clean']],
                'environment_command':['python3','environment.py']}
        return {'components':{'board':'board'},'build':{'recipes':{'target_app':recipe}}}

    def test_environment_handoff_keeps_literal_values_and_explicit_clean(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);data=self.fixture(root)
            with patch.dict('os.environ',{'SDK_OVERRIDE':'existing-sdk','GAR_TARGET':'fixture-board'}):
                run(root,data,'target_app');self.assertEqual([['build'],'literal $(echo no) False','existing-sdk'],json.loads((root/'called.json').read_text()))
                run(root,data,'target_app',clean=True);self.assertEqual([['clean'],'literal $(echo no) True','existing-sdk'],json.loads((root/'called.json').read_text()))

    def test_invalid_recipe_or_foreign_target_runs_no_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);data=self.fixture(root)
            with patch.dict('os.environ',{'GAR_TARGET':'another-board'}),patch('recipe.subprocess.run') as execute:
                with self.assertRaisesRegex(ValueError,'fixed target'):run(root,data,'target_app')
                execute.assert_not_called()
            data['build']['recipes']['target_app']['commands'].append('shell text is not an argv')
            with patch('recipe.subprocess.run') as execute:
                with self.assertRaisesRegex(ValueError,'string array'):run(root,data,'target_app')
                execute.assert_not_called()

    def test_failed_provider_never_starts_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);data=self.fixture(root)
            (root/'environment.py').write_text('raise SystemExit(7)\n')
            with patch.dict('os.environ',{'GAR_TARGET':'fixture-board'}):
                with self.assertRaises(subprocess.CalledProcessError):run(root,data,'target_app')
            self.assertFalse((root/'called.json').exists())

    def test_native_build_failure_and_foreign_staging_preserve_previous_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();output=root/'artifacts/from-codespace';output.mkdir(parents=True)
            manifest=output/'artifact.json';manifest.write_text(json.dumps({'composition':{'product':'fixture'},'target':'fixture-board'}))
            before=manifest.read_bytes()
            product=SimpleNamespace(root=root,id='fixture',board={'id':'fixture-board'},data={'deployment':{}},build=lambda:(_ for _ in ()).throw(ValueError('compiler failed')))
            with self.assertRaisesRegex(ValueError,'compiler failed'):native(product)
            self.assertEqual(before,manifest.read_bytes())
            product.id='another-product'
            with self.assertRaisesRegex(ValueError,'another Product'):native(product,clean=True)
            self.assertEqual(before,manifest.read_bytes())


if __name__=='__main__':unittest.main()
