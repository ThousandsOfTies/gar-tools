from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


WEB_BRIDGE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WEB_BRIDGE_DIR))

from hardware_config import (  # noqa: E402
    GpioLine,
    HardwareConfigError,
    load_hardware_config,
)


GPIO_HEADER = (
    "name,chip,line,direction,role,active,initial,pull,sim_control,description\n"
)


class HardwareConfigTests(unittest.TestCase):
    def test_gpio_polarity_translates_between_logical_and_electrical_state(
        self,
    ) -> None:
        active_high = GpioLine("high", 1, "input", "button", True, "pull-down")
        active_low = GpioLine("low", 2, "input", "button", False, "pull-up")

        self.assertTrue(active_high.electrical_level_for(True))
        self.assertFalse(active_high.electrical_level_for(False))
        self.assertTrue(active_high.active_at_level(True))
        self.assertFalse(active_high.active_at_level(False))

        self.assertFalse(active_low.electrical_level_for(True))
        self.assertTrue(active_low.electrical_level_for(False))
        self.assertFalse(active_low.active_at_level(True))
        self.assertTrue(active_low.active_at_level(False))

    def _write_gpio(
        self,
        hardware_dir: Path,
        rows: list[tuple[str, int, str, str, str, str]],
    ) -> None:
        body = "".join(
            f"{name},/dev/gpiochip0,{line},{direction},{role},{active},,{pull},,test\n"
            for name, line, direction, role, active, pull in rows
        )
        (hardware_dir / "gpio.csv").write_text(
            GPIO_HEADER + body,
            encoding="utf-8",
        )

    def test_unspecified_directory_uses_complete_demo_defaults(self) -> None:
        config = load_hardware_config(None)

        self.assertEqual(config.button_lines, (17, 27))
        self.assertEqual(config.led_lines, (18, 24))
        self.assertEqual(config.rotary.clock, 5)
        self.assertEqual(config.display_dc_line, 16)
        self.assertIsNone(config.source_dir)

    def test_explicit_empty_directory_does_not_invent_demo_hardware(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            config = load_hardware_config(temporary_dir)

        self.assertEqual(config.gpio_lines, ())
        self.assertEqual(config.device_drivers, ())
        self.assertIsNone(config.rotary)
        self.assertIsNone(config.display_dc_line)
        self.assertIsNotNone(config.source_dir)

    def test_headers_only_gpio_csv_is_a_valid_empty_gpio_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            hardware_dir = Path(temporary_dir)
            (hardware_dir / "gpio.csv").write_text(GPIO_HEADER, encoding="utf-8")
            (hardware_dir / "i2c.csv").write_text(
                "name,bus,dev,address,driver,sim,description\n"
                "sensor,1,/dev/i2c-1,0x29,vl53l0x,vl53l0x,test\n",
                encoding="utf-8",
            )

            config = load_hardware_config(hardware_dir)

        self.assertEqual(config.gpio_lines, ())
        self.assertEqual(config.device_drivers, ("vl53l0x",))

    def test_missing_explicit_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            missing = Path(temporary_dir) / "missing"
            with self.assertRaisesRegex(
                HardwareConfigError, "directory does not exist"
            ):
                load_hardware_config(missing)

    def test_csv_drives_rotary_button_and_display_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            hardware_dir = Path(temporary_dir)
            (hardware_dir / "gpio.csv").write_text(
                GPIO_HEADER
                + "encoder_a,/dev/gpiochip0,20,input,encoder,high,,pull-up,,phase A\n"
                + "encoder_b,/dev/gpiochip0,21,input,encoder,high,,pull-up,,phase B\n"
                + "encoder_sw,/dev/gpiochip0,22,input,button,low,,pull-up,,switch\n"
                + "lcd_dc,/dev/gpiochip0,23,output,display_ctrl,high,1,,,DC\n",
                encoding="utf-8",
            )
            (hardware_dir / "spi.csv").write_text(
                "name,bus,chip_select,dev,mode,max_speed_hz,driver,sim,description\n"
                "display,0,0,/dev/spidev0.0,0,40000000,ili9341,ili9341,display\n",
                encoding="utf-8",
            )

            config = load_hardware_config(hardware_dir)

        self.assertEqual(
            (config.rotary.clock, config.rotary.data, config.rotary.switch),
            (20, 21, 22),
        )
        self.assertEqual(config.display_dc_line, 23)
        self.assertEqual(config.button_lines, ())
        self.assertEqual(config.device_drivers, ("ili9341",))

    def test_incomplete_rotary_definition_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            hardware_dir = Path(temporary_dir)
            (hardware_dir / "gpio.csv").write_text(
                GPIO_HEADER
                + "encoder_a,/dev/gpiochip0,20,input,encoder,high,,pull-up,,phase A\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(HardwareConfigError, "incomplete rotary"):
                load_hardware_config(hardware_dir)

    def test_rotary_and_display_control_directions_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hardware_dir = Path(temporary)
            self._write_gpio(
                hardware_dir,
                [
                    ("encoder_a", 20, "output", "encoder", "high", ""),
                    ("encoder_b", 21, "input", "encoder", "high", "pull-up"),
                    ("encoder_sw", 22, "input", "button", "low", "pull-up"),
                ],
            )

            with self.assertRaisesRegex(HardwareConfigError, "must be inputs"):
                load_hardware_config(hardware_dir)

            self._write_gpio(
                hardware_dir,
                [("lcd_dc", 23, "input", "display_ctrl", "high", "")],
            )
            with self.assertRaisesRegex(HardwareConfigError, "must be an output"):
                load_hardware_config(hardware_dir)

    def test_display_dc_role_suffix_is_recognised_and_ambiguity_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            hardware_dir = Path(temporary_dir)
            self._write_gpio(
                hardware_dir,
                [("panel_dc", 23, "output", "display_ctrl", "high", "")],
            )
            self.assertEqual(load_hardware_config(hardware_dir).display_dc_line, 23)

            self._write_gpio(
                hardware_dir,
                [
                    ("lcd_dc", 23, "output", "display_ctrl", "high", ""),
                    ("panel_dc", 24, "output", "display_ctrl", "high", ""),
                ],
            )
            with self.assertRaisesRegex(HardwareConfigError, "multiple display DC"):
                load_hardware_config(hardware_dir)

    def test_empty_sim_column_does_not_enable_a_real_device_driver(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            hardware_dir = Path(temporary_dir)
            (hardware_dir / "gpio.csv").write_text(
                GPIO_HEADER
                + "status_led,/dev/gpiochip0,18,output,led,high,0,,,status\n",
                encoding="utf-8",
            )
            (hardware_dir / "i2c.csv").write_text(
                "name,bus,dev,address,driver,sim,description\n"
                "camera,3,/dev/i2c-3,0x30,sc3336,,real camera\n",
                encoding="utf-8",
            )

            config = load_hardware_config(hardware_dir)

        self.assertEqual((), config.device_drivers)


if __name__ == "__main__":
    unittest.main()
