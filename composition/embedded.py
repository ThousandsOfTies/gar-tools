"""Data-driven PlatformIO preparation/builds; no board or application names."""
from __future__ import annotations

import configparser
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import venv
from pathlib import Path

from product import inside, read_json


def validate(product):
    profile, data = product.profile, product.data
    pio = profile["platformio"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", pio["core_version"]):
        raise ValueError("PlatformIO core version must be pinned")
    if data["build"].get("backend") != "platformio" or profile["startup"]["init"] != "arduino":
        raise ValueError("PlatformIO build/startup mismatch")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", data["build"]["environment"]):
        raise ValueError("Invalid PlatformIO environment")
    project = inside(product.root, data["build"]["project"])
    if not (project / "platformio.ini").is_file():
        raise ValueError("Missing Product PlatformIO composition")
    for path in data["build"]["sources"] + data["build"]["includes"]:
        inside(product.components["application"], path)
    for path in profile["adapter"].values():
        inside(product.components["board"], path)
    if data['hardware'].get('binding_csv'):
        from embedded_binding import derive
        binding = derive(product)
    else:
        binding = read_json(inside(product.root, data["hardware"]["binding"]))
    resources = profile["resources"]
    display = resources["display"]
    if binding.get("schema_version") != 1 or binding["display"] != display["id"]:
        raise ValueError("Display is outside the selected board profile")
    for dimension in ("width", "height"):
        if type(display[dimension]) is not int or not 0 < display[dimension] <= 4096:
            raise ValueError("Invalid board display dimensions")
    buttons = binding["buttons"]
    if not buttons or len(set(buttons)) != len(buttons) or any(key not in resources["buttons"] for key in buttons):
        raise ValueError("Button is outside the selected board profile")
    if binding.get("orientation") != display["orientation"]:
        raise ValueError("Binding must match the board's native display orientation")
    if profile["flash"]["size_bytes"] % (1024 * 1024):
        raise ValueError("Flash size must be a whole number of MiB")
    for path in data["launch"].values():
        inside(product.root, path)
    # Validate all C++ identifiers and values before writing any generated file.
    cpp_namespace("gar_board", resources)
    cpp_namespace("gar_application", data["application"])
    product.binding = binding
    return product


def cpp_namespace(name, values):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid generated C++ identifier")
    lines = [f"namespace {name} {{"]
    for key, value in values.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError("Invalid generated C++ identifier")
        if isinstance(value, dict):
            lines.append(cpp_namespace(key, value))
        elif isinstance(value, bool):
            lines.append(f"inline constexpr bool {key} = {'true' if value else 'false'};")
        elif type(value) is int:
            lines.append(f"inline constexpr int {key} = {value};")
        elif isinstance(value, str):
            lines.append(f"inline constexpr char {key}[] = {json.dumps(value, ensure_ascii=True)};")
        else:
            raise ValueError("Generated constants must be objects, strings, booleans or integers")
    return "\n".join([*lines, "}"])


def prepare(product):
    validate(product)
    if product.data['hardware'].get('binding_csv'):
        relative = product.data['hardware']['binding']
        if relative != '.gar/composition/binding.json':
            raise ValueError('CSV-derived embedded binding must use .gar/composition/binding.json')
        destination = inside(product.root, relative, exists=False)
        if not destination.is_relative_to(product.root / '.gar'):
            raise ValueError('Derived embedded binding escapes generated output')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(product.binding, indent=2) + '\n', encoding='utf-8')
    section = dict(product.profile["platformio"])
    section.pop("core_version")
    size = product.profile["flash"]["size_bytes"] // (1024 * 1024)
    section.update({"board_upload.flash_size": f"{size}MB", "board_build.flash_size": f"{size}MB"})
    section = {key: "\n" + "\n".join(value) if isinstance(value, list) else str(value)
               for key, value in section.items()}
    ini = configparser.ConfigParser(interpolation=None)
    ini["board"] = section
    import io
    stream = io.StringIO()
    ini.write(stream)
    application = product.data["application"]
    sources = [inside(product.components["application"], path) for path in product.data["build"]["sources"]]
    sources.append(inside(product.components["board"], product.profile["adapter"]["source"]))
    source_includes = "\n".join('#include ' + json.dumps(path.as_posix()) for path in sources) + "\n"
    macros = "\n".join(f"#define GAR_APPLICATION_{key.upper()} {json.dumps(value, ensure_ascii=True)}"
                       for key, value in application.items() if type(value) in (int, str))
    files = {"board.ini": stream.getvalue(),
             "gar_composed_sources.h": "// Generated from Product and board declarations.\n" + source_includes,
             "gar_board_config.h": "#pragma once\n" + cpp_namespace("gar_board", product.profile["resources"]) + "\n",
             "application_config.h": "#pragma once\n" + macros + "\n#ifdef __cplusplus\n" +
             cpp_namespace("gar_application", application) + "\n#endif\n"}
    # Windows firmware builds and Linux/WASM builds can share the checkout.
    # Absolute source includes must never overwrite the other host's paths.
    relative = ".gar/composition/" + sys.platform
    output = inside(product.root, relative, exists=False)
    output.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        destination = inside(product.root, relative + "/" + name, exists=False)
        if not destination.is_file() or destination.read_text(encoding="utf-8") != text:
            destination.write_text(text, encoding="utf-8", newline="\n")
    # The fixed, path-free INI is read before PlatformIO runs extra_scripts.
    common_ini = inside(product.root, ".gar/composition/board.ini", exists=False)
    if not common_ini.is_file() or common_ini.read_text(encoding="utf-8") != files["board.ini"]:
        common_ini.write_text(files["board.ini"], encoding="utf-8", newline="\n")
    return output


def runtime_paths(root, version):
    root = Path(root)
    tag = f"{sys.platform}-{platform.machine().lower()}-py{sys.version_info.major}.{sys.version_info.minor}"
    shared = os.environ.get("GAR_BUILD_CACHE")
    if shared:
        base = Path(shared)
        if not base.is_absolute():
            raise ValueError("GAR_BUILD_CACHE must be an absolute build-cache directory")
        runtime = base / "target-build-tools" / f"{tag}-pio-{version}"
        cache = base / "target-build" / tag
    else:
        runtime = root / ".gar/target-build-tools" / f"{tag}-pio-{version}"
        if os.name == "nt":
            # GCC expands response files before spawning cc1plus. Deep ESP-IDF
            # include paths can exceed Windows' process command-line limit.
            identity = hashlib.sha256((str(root.resolve()).casefold()+":"+tag).encode()).hexdigest()[:8]
            cache = Path.home() / ".cache/gar" / identity
        else:
            cache = root / ".cache/gar-target-build" / tag
    python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    env = dict(os.environ, PLATFORMIO_CORE_DIR=str(cache / "core"),
               PLATFORMIO_BUILD_DIR=str(cache / "build"), PLATFORMIO_LIBDEPS_DIR=str(cache / "libdeps"))
    return runtime, python, cache, env


def ensure_toolchain(python, version):
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(python.parent.parent)
    check = subprocess.run([str(python), "-c", f"import platformio; assert platformio.__version__ == '{version}'"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if check.returncode:
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                        f"platformio=={version}"], check=True)


def build(product):
    prepare(product)
    version = product.profile["platformio"]["core_version"]
    _, python, cache, env = runtime_paths(product.root, version)
    ensure_toolchain(python, version)
    subprocess.run([str(python), "-m", "platformio", "run", "-d",
                    str(inside(product.root, product.data["build"]["project"])),
                    "-e", product.data["build"]["environment"]], cwd=product.root, env=env, check=True)
    return cache / "build" / product.data["build"]["environment"]
