"""Render platform-independent Product launch declarations using board profiles."""
from __future__ import annotations

import json
import re
import shlex
import shutil
import struct
from pathlib import Path

from product import inside, read_json


def quote(value):
    return shlex.quote(str(value))


def write(path, text, *, executable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    if executable:
        path.chmod(0o755)


def identity_script(profile):
    identity = profile["identity"]
    lines = [f'test "$(uname -m)" = {quote(identity["architecture"])}']
    if "model" in identity:
        lines.append(f'test "$(tr -d \'\\000\' </proc/device-tree/model)" = {quote(identity["model"])}')
    if "release_file" in identity:
        lines.append(f'grep -qxF {quote(identity["release_marker"])} {quote(identity["release_file"])}')
    if "boot_argument" in identity:
        lines.append(f'grep -qF {quote(identity["boot_argument"])} /proc/cmdline')
    return "\n".join(lines) + "\n"


def configure_script(product):
    """Board-specific values enter through profile data; Product only selects SPI."""
    profile = product.profile
    preparation = profile["preparation"]
    lines = ["#!/bin/sh", "set -eu", 'test "$(id -u)" = 0', identity_script(profile).rstrip()]
    if preparation["kind"] == "luckfox-config-spi":
        config = preparation["config_file"]
        backup = config + ".gar-board-before"
        lines.append(f'test -e {quote(backup)} || cp -p {quote(config)} {quote(backup)}')
        resources = {item["device"]: item for item in profile["spi"]}
        for row in product.spi:
            route = resources[row["dev"]]["routing"]
            # A bus provider's CLI is reusable; selected speed comes from Product CSV.
            command = ["luckfox-config", "spi", "enable", row["bus"], "--sclk", str(route["sclk"]),
                       "--mosi", str(route["mosi"]), "--miso", str(route["miso"] if product.data["hardware"].get("spi_miso", True) else -1), "--cs", str(route["cs"]),
                       "--speed", row["max_speed_hz"]]
            lines += [shlex.join(command), f'test -c {quote(row["dev"])}']
    elif preparation["kind"] == "armbian-overlay":
        name = preparation["name"]
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError("Invalid overlay name")
        boot = preparation["boot_config"]
        lines += ['ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)',
                  "install -d -m 0755 /boot/overlay-user",
                  f'dtc -@ -I dts -O dtb -o /boot/overlay-user/{name}.dtbo "$ROOT/.board/{preparation["overlay"]}"',
                  'staging=$(mktemp -d)', 'trap \'rm -f "$staging/base.dtb" "$staging/merged.dtb" "$staging/dtc.log"; rmdir "$staging"\' EXIT',
                  'dtc -I fs -O dtb -o "$staging/base.dtb" /sys/firmware/devicetree/base 2>"$staging/dtc.log"',
                  f'fdtoverlay -i "$staging/base.dtb" -o "$staging/merged.dtb" /boot/overlay-user/{name}.dtbo',
                  f'test -e {quote(boot + ".gar-board-before")} || cp -p {quote(boot)} {quote(boot + ".gar-board-before")}',
                  "python3 - <<'PY'", "from pathlib import Path", f"file=Path({boot!r})", "lines=file.read_text().splitlines()",
                  "indices=[i for i,line in enumerate(lines) if line.startswith('user_overlays=')]",
                  "if len(indices)>1: raise RuntimeError('Duplicate user_overlays entries')",
                  "if indices:", "    index=indices[0]", "    values=lines[index].split('=',1)[1].split()",
                  f"    if {name!r} not in values: values.append({name!r})", "    lines[index]='user_overlays='+' '.join(values)",
                  f"else: lines.append('user_overlays={name}')", "file.write_text('\\n'.join(lines)+'\\n')", "PY"]
        for row in product.spi:
            lines.append(f'test -c {quote(row["dev"])} || exit 10')
    else:
        raise ValueError("Unsupported board preparation provider")
    return "\n".join(lines) + "\n"


def launch_script(product):
    deployment = product.data["deployment"]
    app = deployment["root"] + "/app"
    runtime = deployment["root"] + "/node/bin/node"
    binary_dir = app + "/" + product.data["build"]["directory"]
    lines = ["#!/bin/sh", "set -eu", f"cd {quote(app)}",
             f'export GAR_HARDWARE_DIR={quote(app + "/" + product.data["hardware"]["physical"])}',
             f'export GAR_BIN_DIR={quote(binary_dir)}', f'test -x {quote(runtime)}']
    if product.profile["startup"]["init"] == "systemd":
        profile = product.board["profiles"][product.data["board_profile"]]
        lines += [f'export GAR_BOARD_PROFILE={quote(app + "/.board/" + profile)}',
                  f'python3 {quote(app + "/.startup/preflight.py")}']
    lines += [f'test -x {quote(binary_dir + "/" + name)}' for name in product.data["build"]["outputs"]]
    devices = sorted({row["chip"] for row in product.gpio} | {row["dev"] for row in product.spi})
    # One shared bounded readiness mechanism; board policy provides the deadline.
    lines += ["attempt=0", "while :; do", "  ready=1"]
    lines += [f'  test -c {quote(device)} || ready=0' for device in devices]
    lines += ['  test "$ready" = 0 || break',
              f'  test "$attempt" -lt {int(product.profile["startup"]["device_wait_seconds"])} || {{ echo "Required device did not appear" >&2; exit 1; }}',
              '  attempt=$((attempt + 1))', "  sleep 1", "done",
              f'exec {quote(runtime)} {quote(app + "/" + product.data["launch"]["entrypoint"])}']
    return "\n".join(lines) + "\n"


def render_service(product):
    deployment = product.data["deployment"]
    tools = product.components["tools"]
    app = deployment["root"] + "/app"
    startup = product.profile["startup"]
    if startup["init"] == "busybox":
        template = (tools / "targets/luckfox-rk3506/provisioning/buildroot-busybox/gar-app@.service").read_text()
        template = template.replace("app=@GAR_APP@", "app=" + product.id)
        template = template.replace('app_dir="/opt/gar/apps/$app"', "app_dir=" + quote(app))
        return startup["prefix"] + "-" + product.id, template
    template = (tools / "targets/raspberry-pi-5/provisioning/raspberry-pi-os-systemd/gar-app@.service").read_text()
    user = deployment["user"]
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", user):
        raise ValueError("Invalid service user")
    template = template.replace("%i", product.id)
    template = template.replace("After=network-online.target", "After=" + startup["after"])
    template = template.replace("Wants=network-online.target\n", "")
    template = template.replace("User=gar", "User=" + user).replace("Group=gar", "Group=" + user)
    template = template.replace("SupplementaryGroups=gpio spi video i2c", "SupplementaryGroups=gpio spi")
    template = template.replace("/opt/gar/apps/" + product.id, app)
    return product.id + ".service", template


def install_script(product, service_name):
    app = product.data["deployment"]["root"] + "/app"
    lines = ["#!/bin/sh", "set -eu", "umask 022", 'test "$(id -u)" = 0',
             identity_script(product.profile).rstrip(), f"cd {quote(app)}",
             "configure_status=0", "./configure-target || configure_status=$?",
             'case "$configure_status" in 0|10) ;; *) exit "$configure_status" ;; esac']
    if product.profile["startup"]["init"] == "busybox":
        lines += [f'if test -x /etc/init.d/{service_name}; then /etc/init.d/{service_name} stop; fi',
                  f'install -m 0755 .startup/{service_name} /etc/init.d/{service_name}',
                  f'/etc/init.d/{service_name} restart']
    else:
        user = product.data["deployment"]["user"]
        for legacy in product.data["deployment"].get("legacy_services", []):
            if not re.fullmatch(r"[a-zA-Z0-9_-]+\.service", legacy) or legacy == service_name:
                raise ValueError("Invalid legacy service migration")
            lines.append(f'if test -f /etc/systemd/system/{legacy}; then systemctl disable --now {legacy}; fi')
        lines += ["getent group gpio >/dev/null || groupadd --system gpio",
                  "getent group spi >/dev/null || groupadd --system spi",
                  f'id {quote(user)} >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin {quote(user)}',
                  f'usermod -a -G gpio,spi {quote(user)}',
                  f'install -m 0644 .startup/{service_name} /etc/systemd/system/{service_name}',
                  "install -m 0644 .startup/devices.rules /etc/udev/rules.d/70-" + product.id + ".rules",
                  "udevadm control --reload-rules", "udevadm trigger --subsystem-match=gpio", "udevadm trigger --subsystem-match=spidev",
                  "systemctl daemon-reload", f'systemctl enable {service_name}',
                  f'if test "$configure_status" = 0; then systemctl restart {service_name}; else echo "Reboot required to enable board I/O"; fi']
    return "\n".join(lines) + "\n"


def verify_binaries(product):
    output = inside(product.root, product.data["build"]["directory"])
    receipt = read_json(output / "composition-build.json")
    if receipt != {"mode": "target", "board": product.board["id"],
                   "profile": product.data["board_profile"], "architecture": product.profile["architecture"]}:
        raise ValueError("Target package requires a build for this board/profile; native checks cannot be deployed")
    architecture = product.profile["architecture"]
    for name in product.data["build"]["outputs"]:
        header = (output / name).read_bytes()[:64]
        bits, machine = (1, 40) if architecture == "armv7l" else (2, 183)
        if header[:6] != b"\x7fELF" + bytes((bits, 1)) or struct.unpack_from("<H", header, 18)[0] != machine:
            raise ValueError(f"Wrong target ELF architecture: {name}")
        if bits == 1 and not struct.unpack_from("<I", header, 36)[0] & 0x400:
            raise ValueError("Expected ARM hard-float ABI")
    return output


def package_product(product, output):
    product.validate()
    binaries = verify_binaries(product)
    destination = inside(product.root, output, exists=False)
    if not any(parent.name in ("artifacts", "build") for parent in (destination, *destination.parents)
               if parent != product.root and product.root in parent.parents):
        raise ValueError("Bundle output must be below Product artifacts/ or build/")
    if destination.exists():
        raise ValueError("Bundle path already exists; choose a new output to preserve immutable artifacts")
    app = destination / "files/app"
    app.mkdir(parents=True)
    ignored = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "node_modules")
    for relative in product.data["payload"]:
        source = inside(product.root, relative)
        target = app / relative
        if source.is_symlink() or source.is_dir() and any(item.is_symlink() for item in source.rglob("*")):
            raise ValueError("Payload symlinks must be resolved explicitly")
        if source.is_dir():
            shutil.copytree(source, target, ignore=ignored)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    board = app / ".board"
    board.mkdir()
    shutil.copyfile(product.components["board"] / "board.json", board / "board.json")
    profile_copy = board / product.board["profiles"][product.data["board_profile"]]
    profile_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(product.profile_path, profile_copy)
    overlay = product.profile["preparation"].get("overlay")
    if overlay:
        source = inside(product.components["board"], overlay)
        (board / overlay).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, board / overlay)
    target_binaries = app / product.data["build"]["directory"]
    target_binaries.mkdir(parents=True, exist_ok=True)
    for name in product.data["build"]["outputs"]:
        shutil.copyfile(binaries / name, target_binaries / name)
        (target_binaries / name).chmod(0o755)
    write(app / "run", launch_script(product), executable=True)
    write(app / "configure-target", configure_script(product), executable=True)
    service_name, service = render_service(product)
    write(app / ".startup" / service_name, service, executable=product.profile["startup"]["init"] == "busybox")
    shutil.copyfile(product.components["tools"] / "composition/preflight.py", app / ".startup/preflight.py")
    devices = [(Path(row["chip"]).name, "gpio", "gpio") for row in product.gpio]
    devices += [(Path(row["dev"]).name, "spidev", "spi") for row in product.spi]
    rules = sorted({f'SUBSYSTEM=="{subsystem}", KERNEL=="{device}", GROUP="{group}", MODE="0660"'
                    for device, subsystem, group in devices})
    write(app / ".startup/devices.rules", "\n".join(rules) + "\n")
    write(app / "install", install_script(product, service_name), executable=True)
    write(app / "composition.json", json.dumps(product.describe(), indent=2) + "\n")
    manifest = {"name": product.id, "target": product.board["id"],
                "deploy": {"app": {"files": [{"src": "files/app", "dest": product.data["deployment"]["root"] + "/app"}]}},
                "composition": product.describe()}
    write(destination / "artifact.json", json.dumps(manifest, indent=2) + "\n")
    return destination
