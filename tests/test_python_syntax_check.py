from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_python_syntax import check_source, is_python_source, python_sources


class PythonSyntaxCheckTest(unittest.TestCase):
    def test_discovers_py_files_and_extensionless_python_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = root / "module.py"
            module.write_text("value = 1\n", encoding="utf-8")
            executable = root / "gar-tool"
            executable.write_text(
                "#!/usr/bin/env python3\nvalue = 2\n", encoding="utf-8"
            )
            shell_script = root / "shell-tool"
            shell_script.write_text("#!/bin/sh\npython3 --version\n", encoding="utf-8")
            generated = root / "build" / "generated.py"
            generated.parent.mkdir()
            generated.write_text("this is not valid Python\n", encoding="utf-8")

            self.assertEqual([executable, module], python_sources([root]))
            self.assertFalse(is_python_source(shell_script))

    def test_invalid_extensionless_script_fails_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "broken-tool"
            script.write_text(
                "#!/usr/bin/env python3\nif True print('broken')\n", encoding="utf-8"
            )

            with self.assertRaises(SyntaxError):
                check_source(script)


if __name__ == "__main__":
    unittest.main()
