import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "audio_probe", Path(__file__).with_name("probe.py")
)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class ProbeTests(unittest.TestCase):
    def settings(self, **values):
        return {"action": "status", "card": "USB_A", "service": "app.service", **values}

    @patch.object(driver, "run")
    def test_read_only_and_independent_bindings(self, run):
        run.return_value = {"exit": 0, "output": ""}
        for card, service in [("USB_A", "app.service"), ("USB_B", "another.service")]:
            run.reset_mock()
            self.assertTrue(
                driver.probe(self.settings(card=card, service=service))["ok"]
            )
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn(["amixer", "-c", card, "scontents"], commands)
            self.assertIn(service, commands[-1])
            self.assertFalse(
                any(
                    args[0] == "aplay" or "sset" in args or "restart" in args
                    for args in commands
                )
            )

    @patch.object(driver, "run")
    def test_speaker_tone_is_bounded_and_has_no_capture(self, run):
        run.return_value = {"exit": 0, "output": ""}
        driver.probe(self.settings(action="speaker-test"))
        args, kwargs = run.call_args_list[0]
        self.assertEqual(args[0][0], "aplay")
        pcm = kwargs["data"]
        self.assertEqual(len(pcm), 48000 * 2 * 0.4)
        self.assertLessEqual(
            max(
                abs(int.from_bytes(pcm[i : i + 2], "little", signed=True))
                for i in range(0, len(pcm), 2)
            ),
            3276,
        )

    @patch.object(driver, "run")
    def test_rejects_invalid_bindings_and_volume_before_commands(self, run):
        for settings in [
            self.settings(card="USB; reboot"),
            self.settings(service="../app.service"),
            self.settings(action="restore-speaker", volume=100),
            self.settings(action="unknown"),
        ]:
            with self.assertRaises(ValueError):
                driver.probe(settings)
        run.assert_not_called()

    @patch.object(driver, "run")
    def test_failures_are_not_success(self, run):
        run.return_value = {"exit": 1, "output": ""}
        self.assertFalse(driver.probe(self.settings())["ok"])

    def test_url_and_token_redacted(self):
        text = driver.sanitize(
            "Live audio failed https://example.com?key=private token=private"
        )
        self.assertNotIn("private", text)


if __name__ == "__main__":
    unittest.main()
