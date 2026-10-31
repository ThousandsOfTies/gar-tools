import importlib.util
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / "targets/linux-device/runtime/gpio-input/python/gar_gpio_debounce.py"
SPEC = importlib.util.spec_from_file_location("gar_gpio_debounce", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DebounceTests(unittest.TestCase):
    def gpio(self, edge="both"):
        return SimpleNamespace(direction="in", edge=edge, bias="pull_up", inverted=False, fd=9, close=Mock())

    def test_zero_does_not_touch_legacy_handle(self):
        MODULE.configure_input_debounce(object(), 0)

    def test_request_preserves_edges_bias_polarity_and_clock(self):
        gpio = self.gpio("falling")
        gpio.inverted = True
        with patch.object(MODULE, "_set_config") as setter:
            MODULE.configure_input_debounce(gpio, 1000)
        fd, config = setter.call_args.args
        self.assertEqual(9, fd)
        self.assertEqual(272, len(config))
        self.assertEqual((0x4 | 0x800 | 0x20 | 0x100 | 0x2, 1), struct.unpack_from("=QI", config))
        self.assertEqual((3, 0, 1000, 1), struct.unpack_from("=IIQQ", config, 32))

    def test_invalid_period_is_rejected_before_ioctl(self):
        for value in (-1, 1000001, True, 1.5, "1000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.configure_input_debounce(self.gpio(), value)

    def test_failure_is_explicit_and_closes_all_inputs(self):
        gpios = [self.gpio(), self.gpio(), self.gpio("falling")]
        with patch.object(MODULE, "_set_config", side_effect=OSError("not supported")):
            with self.assertRaisesRegex(RuntimeError, "GPIO v2"):
                MODULE.configure_inputs(gpios, 1000)
        for gpio in gpios:
            gpio.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
