"""Read-only Linux resource checks, parameterized by a board profile and binding."""
from __future__ import annotations

import csv
import json
import os
import stat
import struct
import time
from pathlib import Path


def check(profile, directory):
    with (Path(directory) / "gpio.csv").open(newline="") as stream:
        chips = {row["chip"] for row in csv.DictReader(stream)}
    with (Path(directory) / "spi.csv").open(newline="") as stream:
        buses = {row["dev"] for row in csv.DictReader(stream)}
    deadline = time.monotonic() + profile["startup"]["device_wait_seconds"]
    for device in sorted(chips | buses):
        while not Path(device).exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        if not stat.S_ISCHR(os.stat(device).st_mode):
            raise ValueError(f"Expected a character device: {device}")
    for resource in profile["gpio"]:
        if resource["device"] not in chips or "label" not in resource:
            continue
        import fcntl
        fd = os.open(resource["device"], os.O_RDONLY)
        try:
            info = bytearray(68)
            fcntl.ioctl(fd, 0x8044B401, info)
        finally:
            os.close(fd)
        _, label, lines = struct.unpack("32s32sI", info)
        if label.rstrip(b"\0").decode() != resource["label"] or ("line_count" in resource and lines != resource["line_count"]):
            raise ValueError("GPIO controller identity differs from the selected board profile")
    for resource in profile["spi"]:
        if resource["device"] in buses and "controller" in resource:
            sysfs = Path("/sys/class/spidev", Path(resource["device"]).name, "device").resolve()
            if resource["controller"] not in str(sysfs):
                raise ValueError("SPI controller identity differs from the selected board profile")


if __name__ == "__main__":
    profile = json.loads(Path(os.environ["GAR_BOARD_PROFILE"]).read_text())
    check(profile, os.environ["GAR_HARDWARE_DIR"])
