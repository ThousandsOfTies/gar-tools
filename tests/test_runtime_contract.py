from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.check_runtime_contract import (
    ContractCheckError,
    find_runtime_root,
    manifest_layout_issues,
)


class RuntimeRootDiscoveryTest(unittest.TestCase):
    def test_finds_sibling_runtime_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            tools_root = workspace / "gar-tools"
            tools_root.mkdir()
            runtime_root = workspace / "GaplessAgentRuntime"
            self._write_runtime_marker(runtime_root)

            self.assertEqual(runtime_root, find_runtime_root(tools_root))

    def test_finds_nested_runtime_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_root = Path(tmp) / "gar-tools"
            tools_root.mkdir()
            runtime_root = tools_root / "GaplessAgentRuntime"
            self._write_runtime_marker(runtime_root)

            self.assertEqual(runtime_root, find_runtime_root(tools_root))

    def test_explicit_invalid_checkout_reports_configuration_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_root = Path(tmp) / "gar-tools"
            tools_root.mkdir()

            with self.assertRaisesRegex(ContractCheckError, "GAR_RUNTIME_ROOT"):
                find_runtime_root(tools_root, Path(tmp) / "missing")

    @staticmethod
    def _write_runtime_marker(runtime_root: Path) -> None:
        marker = runtime_root / "scripts/gar_lib/target/manifest.py"
        marker.parent.mkdir(parents=True)
        marker.touch()


class ManifestLayoutTest(unittest.TestCase):
    def test_reports_when_no_target_manifests_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tools_root = Path(temporary)
            (tools_root / "targets").mkdir()

            issues = manifest_layout_issues(
                tools_root,
                [],
                {"simulator": {"local_docker"}},
            )

        self.assertEqual(1, len(issues))
        self.assertIn("no target manifests found", issues[0])

    def test_accepts_matching_folder_tools_root_and_backend_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_root = Path(tmp)
            self._write_manifest(tools_root, "board")
            manifest = self._manifest("board")

            issues = manifest_layout_issues(
                tools_root,
                [manifest],
                {
                    "codespace": {"local"},
                    "simulator": {"sim"},
                    "target": {"deploy"},
                },
            )

            self.assertEqual([], issues)

    def test_reports_layout_and_missing_category_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_root = Path(tmp)
            self._write_manifest(tools_root, "board", target_id="wrong-id")
            manifest = SimpleNamespace(
                id="wrong-id",
                tools_root="targets/elsewhere",
                default_backends={"simulator": "sim"},
            )

            issues = manifest_layout_issues(
                tools_root,
                [manifest],
                {
                    "codespace": {"local"},
                    "simulator": {"sim"},
                    "target": {"deploy"},
                },
            )

            message = "\n".join(issues)
            self.assertIn("must match folder", message)
            self.assertIn("toolsRoot", message)
            self.assertIn("codespace, target", message)

    def test_reports_unknown_backend_and_category(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tools_root = Path(tmp)
            self._write_manifest(tools_root, "board")
            manifest = SimpleNamespace(
                id="board",
                tools_root="targets/board",
                default_backends={
                    "codespace": "local",
                    "simulator": "missing",
                    "target": "deploy",
                    "unexpected": "backend",
                },
            )

            issues = manifest_layout_issues(
                tools_root,
                [manifest],
                {
                    "codespace": {"local"},
                    "simulator": {"sim"},
                    "target": {"deploy"},
                },
            )

            message = "\n".join(issues)
            self.assertIn("unknown categories: unexpected", message)
            self.assertIn("unknown backend 'missing'", message)

    @staticmethod
    def _write_manifest(
        tools_root: Path, folder: str, *, target_id: str | None = None
    ) -> None:
        path = tools_root / "targets" / folder / "target.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"id": target_id or folder}), encoding="utf-8")

    @staticmethod
    def _manifest(target_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=target_id,
            tools_root=f"targets/{target_id}",
            default_backends={
                "codespace": "local",
                "simulator": "sim",
                "target": "deploy",
            },
        )


if __name__ == "__main__":
    unittest.main()
