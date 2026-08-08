"""Read the hardware CSV files used by the web bridge.

This module intentionally depends only on the Python standard library.  The
bridge process and its tests can therefore share the same parsing and mapping
rules without importing aiohttp.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MIN_GPIO_LINE = 0
MAX_GPIO_LINE = 4095


class HardwareConfigError(ValueError):
    """Raised when a hardware CSV exists but cannot describe valid hardware."""


@dataclass(frozen=True)
class GpioLine:
    name: str
    line: int
    direction: str
    role: str
    active_high: bool
    pull: str

    def electrical_level_for(self, active: bool) -> bool:
        """Translate a logical active/inactive state to the GPIO line level."""
        return active if self.active_high else not active

    def active_at_level(self, electrical_high: bool) -> bool:
        """Translate a GPIO line level to the logical active/inactive state."""
        return electrical_high if self.active_high else not electrical_high


@dataclass(frozen=True)
class RotaryLines:
    clock: int
    data: int
    switch: int


@dataclass(frozen=True)
class HardwareConfig:
    gpio_lines: tuple[GpioLine, ...]
    rotary: RotaryLines | None
    display_dc_line: int | None
    device_drivers: tuple[str, ...]
    source_dir: Path | None

    @property
    def gpio_by_line(self) -> dict[int, GpioLine]:
        return {definition.line: definition for definition in self.gpio_lines}

    @property
    def input_lines(self) -> tuple[int, ...]:
        return tuple(
            definition.line
            for definition in self.gpio_lines
            if definition.direction == "input"
        )

    @property
    def output_lines(self) -> tuple[int, ...]:
        return tuple(
            definition.line
            for definition in self.gpio_lines
            if definition.direction == "output"
        )

    @property
    def led_lines(self) -> tuple[int, ...]:
        return tuple(
            definition.line
            for definition in self.gpio_lines
            if definition.direction == "output" and definition.role == "led"
        )

    @property
    def button_lines(self) -> tuple[int, ...]:
        rotary_switch = self.rotary.switch if self.rotary else None
        return tuple(
            definition.line
            for definition in self.gpio_lines
            if definition.direction == "input"
            and definition.role == "button"
            and definition.line != rotary_switch
        )

    def public_mapping(self) -> dict[str, object]:
        def line_mapping(definition: GpioLine) -> dict[str, object]:
            return {
                "name": definition.name,
                "line": definition.line,
                "activeHigh": definition.active_high,
            }

        rotary = None
        if self.rotary:
            rotary = {
                "clock": self.rotary.clock,
                "data": self.rotary.data,
                "switch": self.rotary.switch,
            }
        return {
            "gpio": {
                "inputs": list(self.input_lines),
                "outputs": list(self.output_lines),
                "buttons": [
                    line_mapping(self.gpio_by_line[line]) for line in self.button_lines
                ],
                "leds": [
                    line_mapping(self.gpio_by_line[line]) for line in self.led_lines
                ],
                "rotary": rotary,
                "displayDc": self.display_dc_line,
            },
            "devices": list(self.device_drivers),
            "source": str(self.source_dir) if self.source_dir else "built-in defaults",
        }


# These values preserve the original linux-device demo when the bridge is run
# directly, without GAR_HARDWARE_DIR.  Once gpio.csv is present, it is the sole
# source of GPIO line assignments.
DEFAULT_GPIO_LINES = (
    GpioLine("power_button", 17, "input", "button", True, "pull-down"),
    GpioLine("status_led", 18, "output", "led", True, ""),
    GpioLine("activity_led", 24, "output", "led", True, ""),
    GpioLine("aux_button", 27, "input", "button", True, "pull-down"),
    GpioLine("encoder_a", 5, "input", "encoder", True, "pull-up"),
    GpioLine("encoder_b", 6, "input", "encoder", True, "pull-up"),
    GpioLine("encoder_sw", 13, "input", "button", False, "pull-up"),
    GpioLine("lcd_dc", 16, "output", "display_ctrl", True, ""),
)
DEFAULT_DEVICE_DRIVERS = (
    "ili9341",
    "mfrc522",
    "ssd1306",
    "st7789",
    "vl53l0x",
)

_ROTARY_NAMES = {
    "clock": ("encoder_a", "rotary_a", "rotary_clk", "ky040_a", "ky040_clk"),
    "data": ("encoder_b", "rotary_b", "rotary_dt", "ky040_b", "ky040_dt"),
    "switch": ("encoder_sw", "rotary_sw", "ky040_sw"),
}
_DISPLAY_DC_NAMES = {"lcd_dc", "display_dc"}


def _normalise_name(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _required_text(row: dict[str, str], field: str, row_number: int) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise HardwareConfigError(f"gpio.csv row {row_number}: {field} is required")
    return value


def _parse_gpio_rows(path: Path) -> tuple[GpioLine, ...]:
    definitions: list[GpioLine] = []
    names: set[str] = set()
    lines: set[int] = set()

    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            required_fields = {"name", "line", "direction", "role", "active"}
            if not reader.fieldnames or not required_fields.issubset(reader.fieldnames):
                missing = sorted(required_fields.difference(reader.fieldnames or ()))
                raise HardwareConfigError(
                    f"{path}: missing required columns: {', '.join(missing)}"
                )

            for row_number, row in enumerate(reader, start=2):
                name = _normalise_name(_required_text(row, "name", row_number))
                direction = _required_text(row, "direction", row_number).lower()
                role = _normalise_name(_required_text(row, "role", row_number))
                active = _required_text(row, "active", row_number).lower()
                pull = (row.get("pull") or "").strip().lower()

                try:
                    line = int(_required_text(row, "line", row_number), 10)
                except ValueError as exc:
                    raise HardwareConfigError(
                        f"gpio.csv row {row_number}: line must be an integer"
                    ) from exc

                if not MIN_GPIO_LINE <= line <= MAX_GPIO_LINE:
                    raise HardwareConfigError(
                        f"gpio.csv row {row_number}: line must be between "
                        f"{MIN_GPIO_LINE} and {MAX_GPIO_LINE}"
                    )
                if direction not in {"input", "output"}:
                    raise HardwareConfigError(
                        f"gpio.csv row {row_number}: direction must be input or output"
                    )
                if active not in {"high", "low"}:
                    raise HardwareConfigError(
                        f"gpio.csv row {row_number}: active must be high or low"
                    )
                if name in names:
                    raise HardwareConfigError(
                        f"gpio.csv row {row_number}: duplicate name {name!r}"
                    )
                if line in lines:
                    raise HardwareConfigError(
                        f"gpio.csv row {row_number}: duplicate GPIO line {line}"
                    )

                names.add(name)
                lines.add(line)
                definitions.append(
                    GpioLine(name, line, direction, role, active == "high", pull)
                )
    except OSError as exc:
        raise HardwareConfigError(f"cannot read {path}: {exc}") from exc

    return tuple(definitions)


def _definition_named(
    definitions: Iterable[GpioLine], aliases: tuple[str, ...]
) -> GpioLine | None:
    aliases_set = set(aliases)
    return next(
        (definition for definition in definitions if definition.name in aliases_set),
        None,
    )


def _rotary_lines(definitions: tuple[GpioLine, ...]) -> RotaryLines | None:
    values = {
        part: _definition_named(definitions, aliases)
        for part, aliases in _ROTARY_NAMES.items()
    }
    present = {part for part, definition in values.items() if definition is not None}
    if not present:
        return None
    if len(present) != len(_ROTARY_NAMES):
        missing = sorted(set(_ROTARY_NAMES).difference(present))
        raise HardwareConfigError(
            "gpio.csv defines an incomplete rotary encoder; missing "
            + ", ".join(missing)
        )
    invalid_directions = [
        part
        for part, definition in values.items()
        if definition is not None and definition.direction != "input"
    ]
    if invalid_directions:
        raise HardwareConfigError(
            "gpio.csv rotary lines must be inputs: "
            + ", ".join(sorted(invalid_directions))
        )
    return RotaryLines(
        clock=values["clock"].line,
        data=values["data"].line,
        switch=values["switch"].line,
    )


def _display_dc_definition(
    definitions: tuple[GpioLine, ...],
) -> GpioLine | None:
    candidates = [
        definition
        for definition in definitions
        if definition.name in _DISPLAY_DC_NAMES
        or (definition.role == "display_ctrl" and definition.name.endswith("_dc"))
    ]
    if len(candidates) > 1:
        names = ", ".join(definition.name for definition in candidates)
        raise HardwareConfigError(
            f"gpio.csv defines multiple display DC lines: {names}"
        )
    if not candidates:
        return None
    candidate = candidates[0]
    if candidate.direction != "output":
        raise HardwareConfigError("gpio.csv display DC line must be an output")
    return candidate


def _device_drivers(hardware_dir: Path) -> tuple[str, ...]:
    drivers: set[str] = set()
    for filename in ("i2c.csv", "spi.csv", "video.csv"):
        path = hardware_dir / filename
        if not path.is_file():
            continue
        try:
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                for row in reader:
                    # Current GAR hardware CSVs use ``sim`` as the explicit
                    # opt-in for a simulated device.  Fall back to ``driver``
                    # only for older files that do not have a sim column.
                    value = row.get("sim") if "sim" in row else row.get("driver")
                    driver = _normalise_name(value or "")
                    if driver:
                        drivers.add(driver)
        except OSError as exc:
            raise HardwareConfigError(f"cannot read {path}: {exc}") from exc
    return tuple(sorted(drivers))


def default_hardware_config() -> HardwareConfig:
    return HardwareConfig(
        gpio_lines=DEFAULT_GPIO_LINES,
        rotary=RotaryLines(clock=5, data=6, switch=13),
        display_dc_line=16,
        device_drivers=DEFAULT_DEVICE_DRIVERS,
        source_dir=None,
    )


def load_hardware_config(hardware_dir: str | Path | None) -> HardwareConfig:
    """Load GAR hardware CSVs, using demo defaults only with no explicit dir."""
    if hardware_dir is None:
        return default_hardware_config()

    source_dir = Path(hardware_dir).expanduser().resolve()
    if not source_dir.is_dir():
        raise HardwareConfigError(
            f"hardware configuration directory does not exist: {source_dir}"
        )
    gpio_path = source_dir / "gpio.csv"
    definitions = _parse_gpio_rows(gpio_path) if gpio_path.is_file() else ()
    display_dc = _display_dc_definition(definitions)
    return HardwareConfig(
        gpio_lines=definitions,
        rotary=_rotary_lines(definitions),
        display_dc_line=display_dc.line if display_dc is not None else None,
        device_drivers=_device_drivers(source_dir),
        source_dir=source_dir,
    )
