from __future__ import annotations

import json
import runpy
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "targets"
    / "luckfox-rv1106"
    / "runtime"
    / "bin"
    / "gar-luckfox-sim-isp-engine"
)


class LuckfoxIspEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = runpy.run_path(str(SCRIPT))

    def test_existing_event_log_is_replayed_without_tell_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            event_log = root / "events.jsonl"
            state_file = root / "state.json"
            apply_log = root / "apply.jsonl"
            event_log.write_text(
                json.dumps(
                    {
                        "type": "change",
                        "item": "BRIGHTNESS",
                        "value": 61,
                        "mode": "EDIT",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            state = self.module["load_initial_state"]()
            self.module["replay_then_follow"](
                event_log,
                state,
                state_file,
                apply_log,
                False,
                False,
            )

            self.assertEqual(61, state["BRIGHTNESS"])
            self.assertEqual(
                61, json.loads(state_file.read_text(encoding="utf-8"))["BRIGHTNESS"]
            )

    def test_non_object_json_event_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            state = self.module["load_initial_state"]()

            self.module["process_line"](
                "[]",
                state,
                root / "state.json",
                root / "apply.jsonl",
                False,
            )

            self.assertEqual(50, state["BRIGHTNESS"])


if __name__ == "__main__":
    unittest.main()
