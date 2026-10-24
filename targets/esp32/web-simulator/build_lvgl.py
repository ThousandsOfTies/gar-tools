#!/usr/bin/env python3
"""Compatibility import and CLI for the board-independent LVGL builder."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location('gar_lvgl_builder', Path(__file__).resolve().parents[3] / 'web-simulator/build_lvgl.py')
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)
# Preserve import users as well as the original command line.
globals().update({name: value for name, value in vars(_shared).items() if not name.startswith('_')})
if __name__ == '__main__':
    main()
