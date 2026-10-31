"""ADB deployment adapter driven by Product composition and machine-local data.

Importing or describing a Product never contacts hardware. Only an explicit
device action uses this adapter. Product source contains no board command logic.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shlex
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path, PureWindowsPath

from package import package_product, render_service, verify_binaries
from product import Product, read_json


class Device:
    def __init__(self, root):
        self.product = Product(root).validate()
        self.root = self.product.root
        path = self.root / ".gar/device.json"
        if not path.is_file():
            raise ValueError("Copy config/device.example.json to .gar/device.json and set the target identity")
        self.machine = read_json(path)
        self.base = self.product.data["deployment"]["root"]
        service, _ = render_service(self.product)
        if self.product.profile["startup"]["init"] != "busybox":
            raise ValueError("This ADB adapter currently supports BusyBox; use the board's selected transport")
        self.service = "/etc/init.d/" + service

    def run(self, args, *, capture=False, check=True):
        return subprocess.run(list(map(str, args)), cwd=self.root, check=check, capture_output=capture,
                              text=True, encoding="utf-8", errors="replace")

    def remote(self, *args, capture=False, check=True):
        return self.run(["adb", "-s", self.machine["serial"], "shell", shlex.join(map(str, args))],
                        capture=capture, check=check)

    def assert_device(self):
        identity = self.product.profile["identity"]
        if self.remote("uname", "-m", capture=True).stdout.strip() != identity["architecture"]:
            raise ValueError("Connected target architecture differs from the selected board profile")
        if "model" in identity:
            model = self.remote("cat", "/proc/device-tree/model", capture=True).stdout.strip("\x00\r\n")
            if model != identity["model"]:
                raise ValueError(f"Connected board model differs from the selected profile: {model!r}")
        if "boot_argument" in identity and identity["boot_argument"] not in self.remote("cat", "/proc/cmdline", capture=True).stdout.split():
            raise ValueError("Connected target boot media differs from the selected board profile")

    def build(self):
        env = os.environ.copy()
        env["GAR_BOARD_SDK"] = str((self.root / self.machine["sdk"]).resolve())
        cli = self.product.components["tools"] / "composition/cli.py"
        if os.name == "nt":
            def linux_path(path):
                value = PureWindowsPath(str(Path(path).resolve()))
                return "/mnt/" + value.drive[0].lower() + "/" + "/".join(value.parts[1:])
            self.run(["wsl", "-d", self.machine["wslDistribution"], "--exec", "env",
                      "GAR_BOARD_SDK=" + linux_path(env["GAR_BOARD_SDK"]), "python3", linux_path(cli),
                      "--root", linux_path(self.root), "build"])
        else:
            subprocess.run(["python3", str(cli), "--root", str(self.root), "build"], env=env, check=True)
        verify_binaries(self.product)

    def node_archive(self):
        node = self.product.data["runtime"]
        cache = self.root / "build/cache" / node["archive"]
        cache.parent.mkdir(parents=True, exist_ok=True)
        if not cache.exists():
            part = cache.with_suffix(cache.suffix + ".part")
            urllib.request.urlretrieve(node["url"], part)
            part.replace(cache)
        if hashlib.sha256(cache.read_bytes()).hexdigest() != node["sha256"]:
            raise ValueError("Runtime archive SHA256 mismatch")
        return cache

    def ensure_runtime(self):
        node = self.product.data["runtime"]
        binary = self.base + "/node/bin/node"
        present = self.remote(binary, "--version", capture=True, check=False)
        if present.returncode == 0 and present.stdout.strip() == "v" + node["version"]:
            return
        archive = self.node_archive()
        runtime = node["archive"].removesuffix(".tar.xz")
        payload = archive.parent / (runtime + "-runtime.tar")
        # BusyBox targets need neither XZ support nor a package manager.
        with tarfile.open(archive, "r:xz") as source, tarfile.open(payload, "w") as package:
            for name in ("bin/node", "LICENSE"):
                member = source.getmember(runtime + "/" + name)
                if not member.isfile():
                    raise ValueError("Runtime archive member must be a regular file")
                member.uid = member.gid = 0
                member.uname = member.gname = "root"
                package.addfile(member, source.extractfile(member))
        target = "/tmp/" + self.product.id + "-runtime.tar"
        self.run(["adb", "-s", self.machine["serial"], "push", payload, target])
        self.remote("mkdir", "-p", self.base)
        self.remote("tar", "-xf", target, "-C", self.base)
        link = shlex.quote(self.base + "/node")
        self.remote("sh", "-c", f"test ! -e {link} || test -L {link}")
        self.remote("ln", "-sfn", runtime, self.base + "/node")
        result = self.remote(binary, "--version", capture=True)
        if result.stdout.strip() != "v" + node["version"]:
            raise ValueError("Installed runtime version mismatch")

    def deploy(self):
        self.assert_device()
        verify_binaries(self.product)
        bundle = package_product(self.product, "build/releases/" + str(time.time_ns()))
        self.ensure_runtime()
        self.remote("sh", "-c", f"if test -x {shlex.quote(self.service)}; then {shlex.quote(self.service)} stop; fi")
        archive = bundle / "deploy.tar"
        executables = {"app/run", "app/configure-target", "app/install",
                       "app/.startup/" + Path(self.service).name}
        executables.update("app/" + self.product.data["build"]["directory"] + "/" + name
                           for name in self.product.data["build"]["outputs"])
        def metadata(member):
            if not (member.isfile() or member.isdir()):
                raise ValueError("Deployment contains an unsupported file type")
            member.uid = member.gid = 0
            member.uname = member.gname = "root"
            # Windows file modes cannot represent executable bits reliably.
            member.mode = 0o755 if member.isdir() or member.name in executables else 0o644
            return member
        with tarfile.open(archive, "w") as package:
            package.add(bundle / "files/app", arcname="app", filter=metadata)
        target = "/tmp/" + self.product.id + "-deploy.tar"
        self.run(["adb", "-s", self.machine["serial"], "push", archive, target])
        self.remote("mkdir", "-p", self.base)
        self.remote("tar", "-xf", target, "-C", self.base)
        self.remote("sh", self.base + "/app/install")
        self.remote(self.service, "status")


def main(root):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "deploy", "up", "start", "stop", "status", "logs", "configure"])
    args = parser.parse_args()
    device = Device(root)
    if args.action in ("build", "up"):
        device.build()
    if args.action in ("deploy", "up"):
        device.deploy()
    if args.action not in ("build", "deploy", "up"):
        device.assert_device()
        if args.action == "logs":
            device.remote("tail", "-n", "100", "/var/log/gar/" + device.product.id + ".log")
        elif args.action == "configure":
            device.remote("sh", device.base + "/app/configure-target")
        else:
            device.remote(device.service, args.action)
