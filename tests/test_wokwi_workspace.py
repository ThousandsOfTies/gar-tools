from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PREPARE_SCRIPT = (
    REPOSITORY_ROOT
    / "targets"
    / "esp32"
    / "wokwi"
    / "m5stackc"
    / "scripts"
    / "prepare_workspace.py"
)


def load_prepare_workspace_module():
    spec = importlib.util.spec_from_file_location(
        "gar_tools_prepare_workspace", PREPARE_SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {PREPARE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prepare_workspace = load_prepare_workspace_module()


class WokwiWorkspaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.template_dir = self.root / "template"
        self.project_dir = self.root / "generated" / "m5stackc"
        self.app_src_dir = self.root / "application" / "src"
        self.app_config_path = self.root / "application" / "wokwi.ini"

        self.template_dir.mkdir()
        self.app_src_dir.mkdir(parents=True)
        self.app_config_path.write_text("[env:m5stackc]\n", encoding="utf-8")
        (self.template_dir / "platformio.ini.template").write_text(
            "[platformio]\nsrc_dir = {app_src}\n{app_config}\n",
            encoding="utf-8",
        )
        (self.template_dir / "wokwi.toml.template").write_text(
            'firmware = "{firmware}"\nelf = "{elf}"\n',
            encoding="utf-8",
        )
        (self.template_dir / "diagram.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def render(self, project_dir: Path | None = None) -> None:
        prepare_workspace.render_workspace(
            self.template_dir,
            project_dir or self.project_dir,
            self.app_src_dir,
            self.app_config_path,
        )

    def test_generates_marked_workspace_with_external_application_source(self) -> None:
        self.render()

        expected_app_src = Path(
            os.path.relpath(self.app_src_dir, self.project_dir)
        ).as_posix()
        platformio = (self.project_dir / "platformio.ini").read_text(encoding="utf-8")
        self.assertIn(f"src_dir = {expected_app_src}", platformio)
        self.assertIn("extra_configs = .gar-app.ini", platformio)
        self.assertEqual(
            self.app_config_path.read_text(encoding="utf-8"),
            (self.project_dir / ".gar-app.ini").read_text(encoding="utf-8"),
        )

        marker = json.loads(
            (self.project_dir / prepare_workspace.WORKSPACE_MARKER).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(prepare_workspace.MARKER_GENERATOR, marker["generator"])
        self.assertEqual(prepare_workspace.MARKER_VERSION, marker["version"])
        self.assertIn("diagram.json", marker["managedFiles"])
        self.assertNotIn(prepare_workspace.WORKSPACE_MARKER, marker["managedFiles"])

    def test_repository_template_generates_a_complete_workspace(self) -> None:
        repository_template = PREPARE_SCRIPT.parents[1]

        prepare_workspace.render_workspace(
            repository_template,
            self.project_dir,
            self.app_src_dir,
            self.app_config_path,
        )

        self.assertTrue((self.project_dir / "diagram.json").is_file())
        self.assertTrue((self.project_dir / "scripts" / "env_flags.py").is_file())
        self.assertTrue((self.project_dir / "platformio.ini").is_file())
        self.assertTrue((self.project_dir / "wokwi.toml").is_file())

    def test_refuses_application_root_and_preserves_its_source(self) -> None:
        application_root = self.app_src_dir.parent
        source_file = self.app_src_dir / "main.cpp"
        source_file.write_text("// application source\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "application source"):
            self.render(application_root)

        self.assertEqual(
            "// application source\n", source_file.read_text(encoding="utf-8")
        )

    def test_refuses_nonempty_unmanaged_directory(self) -> None:
        self.project_dir.mkdir(parents=True)
        user_file = self.project_dir / "README.md"
        user_file.write_text("keep me\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "unmanaged Wokwi workspace"):
            self.render()

        self.assertEqual("keep me\n", user_file.read_text(encoding="utf-8"))

    def test_refuses_workspace_symlink(self) -> None:
        target_dir = self.root / "workspace-target"
        target_dir.mkdir()
        workspace_link = self.root / "workspace-link"
        workspace_link.symlink_to(target_dir, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "must not contain a symlink"):
            self.render(workspace_link)

        self.assertEqual([], list(target_dir.iterdir()))

    def test_refuses_symlink_in_workspace_parent_path(self) -> None:
        target_dir = self.root / "workspace-parent-target"
        target_dir.mkdir()
        parent_link = self.root / "workspace-parent-link"
        parent_link.symlink_to(target_dir, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "must not contain a symlink"):
            self.render(parent_link / "m5stackc")

        self.assertEqual([], list(target_dir.iterdir()))

    def test_regeneration_removes_only_previously_managed_files(self) -> None:
        old_template_file = self.template_dir / "old.txt"
        old_template_file.write_text("old\n", encoding="utf-8")
        self.render()

        build_artifact = self.project_dir / ".pio" / "firmware.bin"
        build_artifact.parent.mkdir()
        build_artifact.write_bytes(b"firmware")
        old_template_file.unlink()
        (self.template_dir / "new.txt").write_text("new\n", encoding="utf-8")

        self.render()

        self.assertFalse((self.project_dir / "old.txt").exists())
        self.assertEqual(
            "new\n", (self.project_dir / "new.txt").read_text(encoding="utf-8")
        )
        self.assertEqual(b"firmware", build_artifact.read_bytes())

    def test_migrates_legacy_marker_without_removing_legacy_source(self) -> None:
        self.project_dir.mkdir(parents=True)
        (self.project_dir / prepare_workspace.WORKSPACE_MARKER).touch()
        (self.project_dir / "platformio.ini").write_text("old\n", encoding="utf-8")
        (self.project_dir / "wokwi.toml").write_text("old\n", encoding="utf-8")
        legacy_source = self.project_dir / "src" / "main.cpp"
        legacy_source.parent.mkdir()
        legacy_source.write_text("// keep legacy source\n", encoding="utf-8")

        self.render()

        self.assertEqual(
            "// keep legacy source\n", legacy_source.read_text(encoding="utf-8")
        )
        marker = json.loads(
            (self.project_dir / prepare_workspace.WORKSPACE_MARKER).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(prepare_workspace.MARKER_VERSION, marker["version"])

    def test_invalid_marker_cannot_name_files_outside_workspace(self) -> None:
        self.project_dir.mkdir(parents=True)
        outside_file = self.project_dir.parent / "outside.txt"
        outside_file.write_text("keep me\n", encoding="utf-8")
        marker = {
            "generator": prepare_workspace.MARKER_GENERATOR,
            "version": prepare_workspace.MARKER_VERSION,
            "managedFiles": ["../../outside.txt"],
        }
        (self.project_dir / prepare_workspace.WORKSPACE_MARKER).write_text(
            json.dumps(marker), encoding="utf-8"
        )

        with self.assertRaisesRegex(
            RuntimeError, "Invalid managed Wokwi workspace path"
        ):
            self.render()

        self.assertEqual("keep me\n", outside_file.read_text(encoding="utf-8"))

    def test_stale_file_removal_refuses_an_intermediate_symlink(self) -> None:
        old_template_dir = self.template_dir / "nested"
        old_template_dir.mkdir()
        old_template_file = old_template_dir / "old.txt"
        old_template_file.write_text("generated\n", encoding="utf-8")
        self.render()

        old_template_file.unlink()
        old_template_dir.rmdir()
        generated_file = self.project_dir / "nested" / "old.txt"
        generated_file.unlink()
        generated_file.parent.rmdir()

        outside_dir = self.root / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "old.txt"
        outside_file.write_text("keep me\n", encoding="utf-8")
        (self.project_dir / "nested").symlink_to(outside_dir, target_is_directory=True)

        with self.assertRaisesRegex(RuntimeError, "workspace symlink"):
            self.render()

        self.assertEqual("keep me\n", outside_file.read_text(encoding="utf-8"))

    def test_staging_failure_leaves_existing_workspace_unchanged(self) -> None:
        self.render()
        generated_diagram = self.project_dir / "diagram.json"
        self.assertEqual("{}\n", generated_diagram.read_text(encoding="utf-8"))

        (self.template_dir / "diagram.json").write_text(
            '{"changed": true}\n', encoding="utf-8"
        )
        (self.template_dir / "wokwi.toml.template").unlink()

        with self.assertRaises(FileNotFoundError):
            self.render()

        self.assertEqual("{}\n", generated_diagram.read_text(encoding="utf-8"))

    def test_install_failure_can_be_recovered_on_the_next_run(self) -> None:
        self.render()
        (self.template_dir / "aaa-new.txt").write_text("new\n", encoding="utf-8")
        (self.template_dir / "diagram.json").write_text(
            '{"changed": true}\n', encoding="utf-8"
        )
        original_install = prepare_workspace.install_file

        def fail_on_diagram(source: Path, destination: Path) -> None:
            if destination.name == "diagram.json":
                raise OSError("injected install failure")
            original_install(source, destination)

        with mock.patch.object(
            prepare_workspace,
            "install_file",
            side_effect=fail_on_diagram,
        ):
            with self.assertRaisesRegex(OSError, "injected install failure"):
                self.render()

        self.assertTrue((self.project_dir / "aaa-new.txt").is_file())
        self.render()
        self.assertEqual(
            '{"changed": true}\n',
            (self.project_dir / "diagram.json").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
