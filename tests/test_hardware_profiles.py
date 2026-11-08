from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "composition"))
from hardware_profiles import generate


class HardwareProfiles(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "canonical"
        self.source.mkdir()
        (self.source / "gpio.csv").write_text(
            'name,chip,line,debounce_us,description\ninput_a,/dev/gpiochip2,20,1000,"phase A, verified"\ninput_b,/dev/gpiochip2,21,1000,phase B\n', encoding="utf-8")
        (self.source / "spi.csv").write_text(
            "name,dev,max_speed_hz,sim\ndisplay,/dev/spidev1.0,8000000,\n", encoding="utf-8")
        self.overrides = self.root / "overrides.csv"
        self.output = self.root / "generated"

    def changes(self, rows):
        self.overrides.write_text("table,name,field,value\n" + rows, encoding="utf-8")

    def rows(self, name):
        with (self.output / (name + ".csv")).open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def test_profile_inherits_binding_and_only_applies_declared_differences(self):
        before = {path.name: path.read_bytes() for path in self.source.iterdir()}
        self.changes("gpio,input_*,debounce_us,0\nspi,display,max_speed_hz,1000000\nspi,display,sim,gc9a01\n")
        generate(self.source, self.overrides, self.output)
        self.assertEqual(["20", "21"], [row["line"] for row in self.rows("gpio")])
        self.assertEqual(["0", "0"], [row["debounce_us"] for row in self.rows("gpio")])
        self.assertEqual("phase A, verified", self.rows("gpio")[0]["description"])
        self.assertEqual("/dev/spidev1.0", self.rows("spi")[0]["dev"])
        self.assertEqual("1000000", self.rows("spi")[0]["max_speed_hz"])
        self.assertEqual("gc9a01", self.rows("spi")[0]["sim"])
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.source.iterdir()})

    def test_regeneration_picks_up_changed_canonical_wiring(self):
        self.changes("gpio,input_*,debounce_us,0\n")
        generate(self.source, self.overrides, self.output)
        path = self.source / "gpio.csv"
        path.write_text(path.read_text(encoding="utf-8").replace(",20,", ",37,"), encoding="utf-8")
        generate(self.source, self.overrides, self.output)
        self.assertEqual("37", self.rows("gpio")[0]["line"])

    def test_invalid_differences_fail_before_creating_output(self):
        for rows in ("other,input_a,line,5\n", "gpio,missing,line,5\n", "gpio,input_a,unknown,5\n",
                     "gpio,input_a,name,renamed\n", "gpio,input_*,line,5\ngpio,input_a,line,6\n"):
            with self.subTest(rows=rows):
                self.changes(rows)
                with self.assertRaises(ValueError):
                    generate(self.source, self.overrides, self.output)
                self.assertFalse(self.output.exists())

    def test_generator_cannot_overwrite_canonical_input(self):
        self.changes("gpio,input_*,debounce_us,0\n")
        with self.assertRaisesRegex(ValueError, "overlap"):
            generate(self.source, self.overrides, self.source)


if __name__ == "__main__":
    unittest.main()
