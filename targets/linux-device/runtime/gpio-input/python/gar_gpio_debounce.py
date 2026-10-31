"""Apply Linux GPIO v2 input debounce to a python-periphery GPIO handle.

Call after configuring edge/bias: periphery property setters replace the line
configuration. Package this module beside the application's Python modules.
"""
from __future__ import annotations

import struct

_SET_CONFIG = 0xC110B40D


def _set_config(fd: int, config: bytearray) -> None:
    import fcntl
    fcntl.ioctl(fd, _SET_CONFIG, config)


def configure_input_debounce(gpio, debounce_us: int) -> None:
    """Request 0..1000000 us; zero leaves the existing backend untouched.

    Nonzero periods require the GPIO v2 character-device backend. Unsupported
    requests fail explicitly rather than silently reverting to unfiltered input.
    """
    if isinstance(debounce_us, bool) or not isinstance(debounce_us, int) or not 0 <= debounce_us <= 1_000_000:
        raise ValueError("debounce_us must be an integer from 0 to 1000000")
    if not debounce_us:
        return
    if gpio.direction != "in":
        raise ValueError("kernel debounce requires an input GPIO")
    # Cdev2GPIO uses CLOCK_REALTIME for its public EdgeEvent timestamps; retain
    # that clock and the public edge, bias and polarity configuration.
    flags = 0x4 | 0x800
    flags |= {"none": 0, "rising": 0x10, "falling": 0x20, "both": 0x30}[gpio.edge]
    flags |= {"default": 0, "pull_up": 0x100, "pull_down": 0x200, "disable": 0x400}[gpio.bias]
    if gpio.inverted:
        flags |= 0x2
    # gpio_v2_line_config: 32-byte header + ten 24-byte attributes. Fixed ABI
    # offsets preserve the kernel's aligned-u64 layout on ARM32 and ARM64.
    config = bytearray(272)
    struct.pack_into("=QI", config, 0, flags, 1)
    struct.pack_into("=IIQQ", config, 32, 3, 0, debounce_us, 1)
    try:
        _set_config(gpio.fd, config)
    except (OSError, NotImplementedError) as error:
        raise RuntimeError(
            "kernel debounce requires Linux GPIO v2; use a compatible backend "
            "or explicitly set the Product debounce period to 0"
        ) from error


def configure_inputs(gpios, debounce_us: int) -> None:
    """Apply one Product-selected period, closing the inputs on failure."""
    try:
        for gpio in gpios:
            configure_input_debounce(gpio, debounce_us)
    except Exception:
        for gpio in gpios:
            gpio.close()
        raise
