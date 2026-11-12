"""Prove a canonical I2C path is a CUSE substitute before simulator commands."""
import os
from pathlib import Path
import re
import stat


def require_virtual_i2c(device):
    if not re.fullmatch(r'/dev/i2c-\d+', str(device)):
        raise ValueError('Invalid I2C device path')
    information=Path(device).stat()
    if not stat.S_ISCHR(information.st_mode):
        raise ValueError('I2C device is not a character device')
    actual=Path(f'/sys/dev/char/{os.major(information.st_rdev)}:{os.minor(information.st_rdev)}').resolve()
    if '/virtual/cuse/' not in str(actual):
        raise ValueError('Simulation requires a CUSE virtual I2C device')
    return str(device)
