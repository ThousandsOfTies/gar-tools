from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "targets"


class TargetProductBoundaryTests(unittest.TestCase):
    def test_target_packs_do_not_name_a_product(self) -> None:
        product_tokens = (
            "garstream",
            "garstreamrx",
            "garstreamtx",
            "gar-stream-rx",
            "gar-stream-tx",
            "garadhocapp",
            "gar-adhoc-app",
            "garviberemote",
            "gar-vibe-remote",
            "vibe remote",
        )

        for path in TARGETS.rglob("*"):
            if not path.is_file() or any(
                part in {".pio", "__pycache__", "build", "node_modules"}
                for part in path.parts
            ):
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(
                    any(token in content for token in product_tokens),
                    f"Product-specific content leaked into Target Pack: {path}",
                )

    def test_known_product_assets_are_not_in_target_packs(self) -> None:
        product_paths = (
            "luckfox-rv1106/app-template",
            "luckfox-rv1106/docs/02_ZERO_DIFF_POLICY.md",
            "luckfox-rv1106/docs/05_RV1106_FEATURE_MENU.md",
            "luckfox-rv1106/docs/06_ROTARY_ISP_RASPI_VIEW.md",
            "luckfox-rv1106/docs/07_SIM_FIRST_ROTARY_UI.md",
            "luckfox-rv1106/docs/08_SIM_MONITOR_OUTPUT.md",
            "luckfox-rv1106/runtime/bin/gar-luckfox-sim-control-loop",
            "luckfox-rv1106/runtime/bin/gar-luckfox-sim-isp-engine",
            "luckfox-rv1106/runtime/bin/gar-luckfox-sim-monitor",
            "luckfox-rv1106/runtime/bin/gar-luckfox-sim-rotary-ui",
            "luckfox-rv1106/scripts/luckfox_push_rtsp.sh",
            "luckfox-rv1106/scripts/raspi_run_mediatx.sh",
            "luckfox-rv1106/scripts/raspi_view_rtsp.sh",
            "esp32/probes/spp-jsonl",
            "linux-device/runtime/web-bridge/components/video-transmitter.js",
        )

        for relative_path in product_paths:
            with self.subTest(path=relative_path):
                self.assertFalse((TARGETS / relative_path).exists())


if __name__ == "__main__":
    unittest.main()
