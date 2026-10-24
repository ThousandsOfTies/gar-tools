#!/usr/bin/env python3
"""Serve or export a Product panel with reusable GAR simulator components."""
from __future__ import annotations

import argparse
import functools
import json
import mimetypes
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
BOARD_ROOT = ROOT.parent / 'targets/esp32/web-simulator/components'
LEGACY_COMPONENTS = {'twatch-2020.mjs', 'lvgl-surface.mjs', 'framebuffer.mjs'}
PUBLIC_EXTENSIONS = {'.html', '.css', '.js', '.mjs', '.json', '.svg', '.png', '.ico', '.woff2', '.wasm'}
mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('application/wasm', '.wasm')


def public_file(root: Path, relative: str) -> Path | None:
    parts = relative.replace('\\', '/').split('/')
    if any(part.startswith('.') or ':' in part for part in parts if part):
        return None
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root.resolve()):
        return None
    if candidate.is_file() and candidate.suffix.lower() in PUBLIC_EXTENSIONS:
        return candidate
    return None


def export_panel(panel: Path, destination: Path) -> None:
    panel, destination = panel.resolve(), destination.resolve()
    if destination == panel or panel.is_relative_to(destination) or destination.is_relative_to(panel):
        raise ValueError('Export directory must be separate from the panel directory.')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Export directory must be empty; existing output is never deleted.')
    if not public_file(panel, 'index.html'):
        raise ValueError('Panel must contain index.html.')
    assets = []
    for source in panel.rglob('*'):
        relative = source.relative_to(panel).as_posix()
        if not public_file(panel, relative):
            continue
        if relative.split('/')[0] == 'gar-components' or relative in {
                'components/' + name for name in LEGACY_COMPONENTS}:
            raise ValueError('gar-components and legacy simulator module paths are reserved.')
        assets.append((source, destination / relative))
    for relative, source in component_assets().items():
        assets.append((source, destination / 'gar-components' / relative))
        if relative in LEGACY_COMPONENTS:
            assets.append((source, destination / 'components' / relative))
    for source, target in assets:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def component_file(relative: str) -> Path | None:
    return public_file(ROOT / 'components', relative) or public_file(BOARD_ROOT, relative)


def component_assets():
    assets = {}
    for root in (BOARD_ROOT, ROOT / 'components'):
        for source in root.rglob('*'):
            relative = source.relative_to(root).as_posix()
            if public_file(root, relative):
                assets[relative] = source
    return assets


class PanelHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, panel: Path, **kwargs):
        self.panel = panel.resolve()
        super().__init__(*args, **kwargs)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/healthz':
            body = json.dumps({'ok': True, 'surface': 'gar-web-simulator'}).encode()
            mime = 'application/json'
        else:
            if path.startswith('/gar-components/'):
                source = component_file(path.removeprefix('/gar-components/'))
            elif path.startswith('/components/') and path.removeprefix('/components/') in LEGACY_COMPONENTS:
                source = component_file(path.removeprefix('/components/'))
            else:
                source = public_file(self.panel, path.lstrip('/') or 'index.html')
            if source is None:
                self.send_error(404)
                return
            body = source.read_bytes()
            mime = mimetypes.guess_type(source.name)[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)


def main(*, default_panel: Path | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel', type=Path, default=default_panel or ROOT / 'panel')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--export', dest='destination', type=Path)
    args = parser.parse_args()
    if not public_file(args.panel, 'index.html'):
        parser.error('--panel must contain a public index.html')
    if args.destination:
        try:
            export_panel(args.panel, args.destination)
        except ValueError as error:
            parser.error(str(error))
        print(f'Exported simulator: {args.destination.resolve()}')
        return
    handler = functools.partial(PanelHandler, panel=args.panel)
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f'GAR simulator: http://{args.host}:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
