import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("audio_state_recipe", Path(__file__).with_name("configure.py"))
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


class AudioStateTests(unittest.TestCase):
    def test_invalid_binding_does_not_run_commands(self):
        with patch.object(recipe, "run") as run:
            for value in [
                dict(card="USB;reboot", usbId="3206:104f", playbackPercent=30),
                dict(card="USB", usbId="3206:104f", playbackPercent=80),
                dict(card="USB", usbId="*:*", playbackPercent=30),
            ]:
                with self.assertRaises(ValueError):
                    recipe.configure(value)
            run.assert_not_called()

    def test_rule_only_restores_exact_usb_product(self):
        rule = recipe.restore_rule("3206:104f")
        self.assertIn('ATTRS{idVendor}=="3206"', rule)
        self.assertIn('ATTRS{idProduct}=="104f"', rule)
        self.assertIn('KERNEL=="controlC[0-9]*"', rule)
        self.assertIn("restore $attr{device/number}", rule)
        self.assertNotIn("amixer", rule)

    def test_real_restoration_check_and_mic_controls_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def mapped(name):
                return root / str(name).lstrip("/")

            card = mapped("/proc/asound/card2")
            card.mkdir(parents=True)
            (card / "id").write_text("USB_A\n")
            (card / "usbid").write_text("3206:104f\n")
            mapped("/etc/udev/rules.d").mkdir(parents=True)
            mapped("/var/lib").mkdir(parents=True)
            mapped("/var/lib/alsa").mkdir()
            commands = []

            def command(args):
                commands.append(args)
                if args == ["alsactl", "store", "USB_A"]:
                    mapped("/var/lib/alsa/asound.state").write_text("state.USB_A {}")
                if args == ["amixer", "-c", "USB_A", "sget", "PCM"]:
                    return "Front Left: Playback 30 [30%] [on]\nFront Right: Playback 30 [30%] [on]"
                return ""

            with (
                patch.object(recipe, "Path", side_effect=mapped),
                patch.object(recipe.os, "geteuid", return_value=0, create=True),
                patch.object(recipe.shutil, "which", return_value="/bin/tool"),
                patch.object(recipe, "run", side_effect=command),
            ):
                result = recipe.configure(dict(card="USB_A", usbId="3206:104f", playbackPercent=30))
            self.assertTrue(result["restoreVerified"])
            zero = commands.index(["amixer", "-c", "USB_A", "sset", "PCM", "0%"])
            restored = commands.index(["alsactl", "restore", "USB_A"])
            self.assertLess(zero, restored)
            self.assertTrue(all("Mic" not in command for command in commands))


if __name__ == "__main__":
    unittest.main()
