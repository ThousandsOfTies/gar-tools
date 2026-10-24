#!/usr/bin/env python3
"""Compatibility entrypoint for the T-Watch bench; shared server lives at the root."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('gar_web_simulator', ROOT.parents[2] / 'web-simulator/serve.py')
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)
PanelHandler = _shared.PanelHandler
ThreadingHTTPServer = _shared.ThreadingHTTPServer
public_file = _shared.public_file
export_panel = _shared.export_panel


def main():
    _shared.main(default_panel=ROOT / 'panel')


if __name__ == '__main__':
    main()
