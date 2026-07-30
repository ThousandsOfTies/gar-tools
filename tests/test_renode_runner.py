from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = (
    REPOSITORY_ROOT / "targets" / "esp32" / "renode" / "m5status-tiny" / "run.py"
)


def load_runner_module():
    spec = importlib.util.spec_from_file_location(
        "gar_tools_renode_runner", RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_runner_module()


class RenodeVersionTest(unittest.TestCase):
    def test_accepts_comma_version_banner_with_build_suffix(self) -> None:
        output = "Renode, version 1.16.1.17033 (d66b0c2a-202602160923)"

        self.assertTrue(runner.has_required_renode_version(output))

    def test_accepts_short_version_banner_with_build_suffix(self) -> None:
        output = "Renode v1.16.1.17033\nbuild: d66b0c2a-202602160923"

        self.assertTrue(runner.has_required_renode_version(output))

    def test_accepts_release_version_without_build_suffix(self) -> None:
        self.assertTrue(runner.has_required_renode_version("Renode, version 1.16.1"))

    def test_rejects_a_different_patch_version(self) -> None:
        self.assertFalse(runner.has_required_renode_version("Renode, version 1.16.0"))

    def test_rejects_a_longer_version_with_the_same_prefix(self) -> None:
        self.assertFalse(runner.has_required_renode_version("Renode, version 1.16.10"))

    def test_version_check_returns_the_executable_that_was_checked(self) -> None:
        completed = mock.Mock(
            returncode=0,
            stdout="Renode, version 1.16.1",
            stderr="",
        )
        with (
            mock.patch.object(
                runner.shutil,
                "which",
                return_value="/opt/renode/bin/renode",
            ),
            mock.patch.object(
                runner.subprocess,
                "run",
                return_value=completed,
            ) as run,
        ):
            executable = runner.require_renode_version()

        self.assertEqual("/opt/renode/bin/renode", executable)
        self.assertEqual(
            ["/opt/renode/bin/renode", "--version"],
            run.call_args.args[0],
        )


class RenodeTestExecutableTest(unittest.TestCase):
    def test_prefers_launcher_beside_the_checked_renode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bin_directory = Path(temporary)
            renode = bin_directory / "renode"
            renode_test = bin_directory / "renode-test"
            renode.write_text("#!/bin/sh\n", encoding="utf-8")
            renode_test.write_text("#!/bin/sh\n", encoding="utf-8")
            renode.chmod(0o755)
            renode_test.chmod(0o755)

            with mock.patch.object(
                runner.shutil,
                "which",
                return_value="/different/install/renode-test",
            ) as which:
                selected = runner.find_renode_test_executable(str(renode))

        self.assertEqual(str(renode_test), selected)
        which.assert_not_called()

    def test_falls_back_to_path_when_the_checked_install_has_no_test_runner(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            renode = Path(temporary) / "renode"
            renode.write_text("#!/bin/sh\n", encoding="utf-8")
            renode.chmod(0o755)

            with mock.patch.object(
                runner.shutil,
                "which",
                return_value="/usr/local/bin/renode-test",
            ):
                selected = runner.find_renode_test_executable(str(renode))

        self.assertEqual("/usr/local/bin/renode-test", selected)


if __name__ == "__main__":
    unittest.main()
