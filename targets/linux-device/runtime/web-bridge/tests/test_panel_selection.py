from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


WEB_BRIDGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_BRIDGE_DIR))

try:
    import aiohttp  # noqa: F401
except ModuleNotFoundError:
    bridge = None
else:
    import bridge  # noqa: E402


@unittest.skipUnless(bridge is not None, "bridge tests require aiohttp")
class PanelSelectionTests(unittest.TestCase):
    def test_configured_application_panel_replaces_default_panel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            application_panel = root / "app-panel"
            application_panel.mkdir()
            (application_panel / "index.html").write_text("application", encoding="utf-8")
            config = root / "panel-dir"
            config.write_text(f"{application_panel}\n", encoding="utf-8")

            with patch.object(bridge, "PANEL_DIR_CONFIG", config):
                self.assertEqual(application_panel, bridge._active_panel_dir())

    def test_invalid_panel_setting_keeps_builtin_panel_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            config = Path(temporary_dir) / "panel-dir"
            config.write_text("relative-panel\n", encoding="utf-8")

            with patch.object(bridge, "PANEL_DIR_CONFIG", config):
                self.assertEqual(bridge.PANEL_DIR, bridge._active_panel_dir())

    def test_product_component_is_resolved_after_shared_component(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            application_panel = root / "app-panel"
            product_components = application_panel / "components"
            product_components.mkdir(parents=True)
            product_component = product_components / "servo.js"
            product_component.write_text("product", encoding="utf-8")
            config = root / "panel-dir"
            config.write_text(f"{application_panel}\n", encoding="utf-8")

            with patch.object(bridge, "PANEL_DIR_CONFIG", config):
                self.assertEqual(
                    product_component,
                    bridge._resolve_panel_request("components/servo.js"),
                )
                self.assertEqual(
                    bridge.COMPONENTS_DIR / "bridge-status.js",
                    bridge._resolve_panel_request("components/bridge-status.js"),
                )


if __name__ == "__main__":
    unittest.main()
