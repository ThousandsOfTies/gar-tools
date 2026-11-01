#!/usr/bin/env python3
"""Build an LVGL 7 application as a browser module for any display size."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
PORT_EXPORTS = ['gar_lv_init', 'gar_lv_tick', 'gar_lv_pointer', 'gar_lv_cancel',
                'gar_lv_framebuffer', 'gar_lv_frame', 'gar_lv_width', 'gar_lv_height']
LEGACY_APP_EXPORTS = ['gar_app_init', 'gar_app_receive', 'gar_app_hardware',
                      'gar_app_reset', 'gar_app_refresh', 'gar_app_side_button',
                      'gar_app_scroll', 'gar_app_snapshot', 'gar_app_take_action']
EXPORTS = [*PORT_EXPORTS, *LEGACY_APP_EXPORTS, 'malloc', 'free']

def source_digest(app, config):
    """Identify UI sources and the generic browser port, excluding generated output."""
    digest = hashlib.sha256()
    sources = sorted(path for path in app.iterdir() if path.suffix in {'.c', '.cpp', '.h', '.hpp'})
    for source in [*sources, config, ROOT / 'lvgl/web-port.c', Path(__file__)]:
        digest.update(source.name.encode())
        digest.update(source.read_bytes())
    return digest.hexdigest()

def positive_dimension(value):
    number = int(value)
    if not 1 <= number <= 32767:
        raise argparse.ArgumentTypeError('must be between 1 and 32767 (LVGL 7 coordinates)')
    return number


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    library = p.add_mutually_exclusive_group(required=True)
    library.add_argument('--library', type=Path, help='Legacy LilyGO library root containing src/lvgl')
    library.add_argument('--lvgl', type=Path, help='Standalone LVGL 7 root containing lvgl.h and src/')
    p.add_argument('--json-library', type=Path, help='Optional ArduinoJson root; adds its src/ include directory')
    p.add_argument('--include', type=Path, action='append', default=[], help='Additional include directory (repeatable)')
    p.add_argument('--app', type=Path, required=True, help='Application source directory')
    p.add_argument('--entry', type=Path, help='Application entry source (default: APP/web-entry.cpp)')
    p.add_argument('--source', type=Path, action='append', default=[], help='Additional application source (repeatable)')
    p.add_argument('--app-api', choices=['legacy', 'minimal', 'none'], default='legacy',
                   help='Export the legacy gar_app_* API, only gar_app_init, or no application hooks')
    p.add_argument('--export', action='append', default=[], help='Additional C function to export, without leading underscore')
    p.add_argument('--config', type=Path, required=True, help='LVGL configuration header')
    p.add_argument('--width', type=positive_dimension, default=240)
    p.add_argument('--height', type=positive_dimension, default=240)
    p.add_argument('--buffer-rows', type=positive_dimension, default=24)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--emcc', default='emcc')
    p.add_argument('--emxx', help='C++ linker (default: em++ alongside --emcc)')
    p.add_argument('--jobs', type=int, default=4)
    return p


def build(a):
    app = a.app.resolve()
    lvgl = a.lvgl.resolve() if a.lvgl else a.library.resolve() / 'src/lvgl'
    config = a.config.resolve()
    entry = a.entry.resolve() if a.entry else app / 'web-entry.cpp'
    if not (lvgl / 'lvgl.h').is_file() or not (lvgl / 'src').is_dir():
        raise ValueError('Expected an LVGL 7 root containing lvgl.h and src/')
    if not entry.is_file():
        raise ValueError(f'Application entry source does not exist: {entry}')
    if not config.is_file():
        raise ValueError(f'LVGL configuration does not exist: {config}')
    if a.jobs < 1:
        raise ValueError('--jobs must be positive')
    includes = [lvgl.parent, lvgl, app, *[path.resolve() for path in a.include]]
    if a.json_library:
        includes.append(a.json_library.resolve() / 'src')
    for directory in includes:
        if not directory.is_dir():
            raise ValueError(f'Include directory does not exist: {directory}')
    sources = list(dict.fromkeys([
        *sorted((lvgl / 'src').rglob('*.c')), *sorted(app.glob('*.c')),
        ROOT / 'lvgl/web-port.c', entry, *[path.resolve() for path in a.source],
    ]))
    a.cache.mkdir(parents=True, exist_ok=True)
    a.output.mkdir(parents=True, exist_ok=True)
    flags = ['-O2', *['-I' + str(path) for path in includes],
             '-DLV_CONF_PATH=' + str(config), f'-DGAR_LV_WIDTH={a.width}',
             f'-DGAR_LV_HEIGHT={a.height}', f'-DGAR_LV_BUFFER_ROWS={a.buffer_rows}',
             '-Wno-unused-command-line-argument']
    compiler = subprocess.check_output([a.emcc, '--version'], text=True)
    headers = hashlib.sha256()
    header_paths = {config}
    header_roots = [lvgl, app, *[path.resolve() for path in a.include]]
    if a.json_library:
        header_roots.append(a.json_library.resolve() / 'src')
    for directory in header_roots:
        header_paths.update(path for path in directory.rglob('*') if path.suffix in {'.h', '.hpp'})
    # LilyGO ships a config header outside lvgl/. Standalone LVGL needs only --config.
    if (lvgl.parent / 'lv_conf.h').is_file():
        header_paths.add(lvgl.parent / 'lv_conf.h')
    # Existing apps include their shared .cpp implementation from web-entry.cpp.
    header_paths.update(app.glob('*.cpp'))
    for header in sorted(header_paths):
        headers.update(str(header).encode())
        headers.update(header.read_bytes())
    signature = headers.digest() + compiler.encode() + str(flags).encode()

    def compile_source(source):
        key = hashlib.sha256(signature + source.read_bytes() + str(source).encode()).hexdigest()
        obj = a.cache / (key + '.o')
        if not obj.exists():
            standard = '-std=c++17' if source.suffix in {'.cpp', '.cc', '.cxx'} else '-std=c99'
            subprocess.run([a.emcc, *flags, standard, '-c', str(source), '-o', str(obj)], check=True)
        return obj
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        objects = list(pool.map(compile_source, sources))
    app_exports = LEGACY_APP_EXPORTS if a.app_api == 'legacy' else ['gar_app_init'] if a.app_api == 'minimal' else []
    exports = list(dict.fromkeys([*PORT_EXPORTS, *app_exports, *a.export, 'malloc', 'free']))
    emcc = Path(a.emcc)
    linker = a.emxx or str(emcc.with_name(emcc.name.replace('emcc', 'em++')))
    subprocess.run([linker, *map(str, objects), '-O2',
                    '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sEXPORT_NAME=createLvglUi',
                    '-sENVIRONMENT=web,node', '-sALLOW_MEMORY_GROWTH=1',
                    '-sEXPORTED_FUNCTIONS=' + json.dumps(['_' + name for name in exports]),
                    '-sEXPORTED_RUNTIME_METHODS=' + json.dumps(['ccall', 'UTF8ToString', 'HEAPU8']),
                    '-o', str(a.output / 'lvgl-ui.mjs')], check=True)
    metadata = {'engine': 'LVGL', 'sourceHash': source_digest(app, config),
                'width': a.width, 'height': a.height, 'appApi': a.app_api}
    (a.output / 'build.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print('Built shared LVGL UI:', a.output)

def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        build(args)
    except ValueError as error:
        p.error(str(error))


if __name__ == '__main__':
    main()
