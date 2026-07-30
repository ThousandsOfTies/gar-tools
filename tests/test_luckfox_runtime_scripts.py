from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_BIN = REPOSITORY_ROOT / "targets" / "luckfox-rv1106" / "runtime" / "bin"
CAMERA_STOP = RUNTIME_BIN / "gar-luckfox-ec2-camera-stop"
DEVFS_START = RUNTIME_BIN / "gar-luckfox-ec2-devfs-start"


class LuckfoxRuntimeScriptTest(unittest.TestCase):
    def test_camera_stop_ignores_zero_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "camera_ffmpeg.pid").write_text("0\n", encoding="utf-8")

            result = subprocess.run(
                ("bash", str(CAMERA_STOP)),
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "GAR_RUNTIME_DIR": str(run_dir)},
            )

        self.assertEqual(0, result.returncode)
        self.assertIn("ignoring invalid feeder PID", result.stdout)

    def test_devfs_start_leaves_socket_liveness_decision_to_bridge(self) -> None:
        script = DEVFS_START.read_text(encoding="utf-8")

        self.assertNotIn('rm -f "$sock_path"', script)
        self.assertIn("bridge.py probes an existing socket", script)


if __name__ == "__main__":
    unittest.main()
