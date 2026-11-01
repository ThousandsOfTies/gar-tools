"""Compose a Product from independently pinned application, tools and board repos.

Board profiles describe resources and platform facts. Product CSVs select uses.
This module performs offline validation and builds; it never contacts a board.
"""
from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def inside(root, relative, *, exists=True):
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError(f"Expected a repository-relative path: {relative!r}")
    result = (root / relative).resolve()
    if result == root or root not in result.parents:
        raise ValueError(f"Path escapes repository: {relative}")
    if exists and not result.exists():
        raise ValueError(f"Missing composition input: {result}")
    return result


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class Product:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.data = read_json(self.root / "product.json")
        if self.data.get("schema_version") != 1:
            raise ValueError("Unsupported Product composition schema")
        self.id = self.data["id"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", self.id):
            raise ValueError("Invalid Product id")
        self.components = {key: inside(self.root, self.data["components"][key])
                           for key in ("application", "tools", "board")}
        self.board = read_json(self.components["board"] / "board.json")
        if self.board.get("schema_version") != 1:
            raise ValueError("Unsupported board schema")
        self.profile_path = inside(self.components["board"], self.board["profiles"][self.data["board_profile"]])
        self.profile = read_json(self.profile_path)
        if self.profile.get("schema_version") != 1 or self.profile["board"] != self.board["id"]:
            raise ValueError("Board/profile identity mismatch")
        self.kind = self.profile.get("kind", "linux")
        if self.kind == "platformio":
            self.hardware = inside(self.root, self.data["hardware"]["binding"]).parent
            self.gpio, self.spi = [], []
        elif self.kind == "linux":
            self.hardware = inside(self.root, self.data["hardware"]["physical"])
            self.gpio = csv_rows(self.hardware / "gpio.csv")
            self.spi = csv_rows(self.hardware / "spi.csv")
        else:
            raise ValueError(f"Unsupported board profile kind: {self.kind}")

    def validate(self):
        if self.kind == "platformio":
            from embedded import validate
            return validate(self)
        gpio = {item["device"]: item for item in self.profile["gpio"]}
        used = set()
        for row in self.gpio:
            key = row["chip"], int(row["line"])
            if key in used:
                raise ValueError(f"GPIO line used twice: {key}")
            used.add(key)
            if key[0] not in gpio or key[1] not in gpio[key[0]]["lines"]:
                raise ValueError(f"GPIO is outside the selected board profile: {key}")
            if row["direction"] not in ("input", "output"):
                raise ValueError("Invalid GPIO direction")
            if not 0 <= int(row.get("debounce_us") or 0) <= 1_000_000:
                raise ValueError("Invalid GPIO debounce period")
        buses = {item["device"]: item for item in self.profile["spi"]}
        seen = set()
        for row in self.spi:
            resource = buses.get(row["dev"])
            if not resource or row["dev"] in seen:
                raise ValueError(f"Missing or duplicate board SPI resource: {row['dev']}")
            seen.add(row["dev"])
            if (int(row["bus"]), int(row["chip_select"])) != (resource["bus"], resource["chip_select"]):
                raise ValueError("SPI device/bus/CS mismatch")
            if int(row["mode"]) not in resource["modes"] or not 0 < int(row["max_speed_hz"]) <= resource["max_speed_hz"]:
                raise ValueError("SPI mode/speed exceeds board capability")
        if self.profile["startup"]["init"] not in ("busybox", "systemd"):
            raise ValueError("Unsupported init system")
        for item in self.data["payload"]:
            inside(self.root, item)
        inside(self.components["application"], self.data["build"]["script"])
        inside(self.root, self.data["launch"]["entrypoint"])
        for field in ("root",):
            value = self.data["deployment"][field]
            if not re.fullmatch(r"/opt/[A-Za-z0-9_/-]+", value) or ".." in value.split("/"):
                raise ValueError("Deployment root must be an explicit directory under /opt")
        for name in self.data["build"]["outputs"]:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                raise ValueError("Invalid binary name")
        runtime = self.data.get("runtime")
        if runtime:
            if not re.fullmatch(r"node-v[0-9.]+-linux-arm(?:64|v7l)\.tar\.xz", runtime["archive"]):
                raise ValueError("Invalid runtime archive name")
            if not re.fullmatch(r"[a-f0-9]{64}", runtime["sha256"]):
                raise ValueError("Runtime SHA256 must be pinned")
            if not runtime["url"].startswith("https://"):
                raise ValueError("Runtime download requires HTTPS")
        return self

    def describe(self):
        self.validate()
        components = {}
        for key, directory in self.components.items():
            result = subprocess.run(["git", "-C", str(directory), "rev-parse", "HEAD"],
                                    capture_output=True, text=True, check=False)
            status = subprocess.run(["git", "-C", str(directory), "status", "--porcelain"],
                                    capture_output=True, text=True, check=False)
            components[key] = {"path": self.data["components"][key],
                               "commit": result.stdout.strip() if result.returncode == 0 else "unknown",
                               "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None}
        validated = ({"display": self.binding["display"], "buttons": self.binding["buttons"]}
                     if self.kind == "platformio" else {"gpio_lines": len(self.gpio), "spi_devices": len(self.spi)})
        return {"product": self.id, "components": components, "board": self.board["id"],
                "profile": self.data["board_profile"], "os": self.profile["os"],
                "architecture": self.profile["architecture"], "init": self.profile["startup"]["init"],
                "hardware": self.data["hardware"], "launch": self.data["launch"],
                "validated": validated}

    def prepare(self):
        if self.kind != "platformio":
            raise ValueError("Preparation files are only needed for PlatformIO profiles")
        from embedded import prepare
        return prepare(self)

    def hardware_for(self, environment):
        if self.kind == "platformio":
            if environment not in ("physical", "simulation"):
                raise ValueError(f"Unknown hardware environment: {environment}")
            return self.hardware
        if environment == "physical":
            return self.hardware
        if environment != "simulation":
            raise ValueError(f"Unknown hardware environment: {environment}")
        settings = self.data["hardware"]
        if not settings.get("simulation_overrides"):
            # Existing Products with an independent simulation binding remain valid.
            return inside(self.root, settings["simulation"])
        relative = settings["simulation"]
        output = inside(self.root, relative, exists=False)
        if Path(relative).parts[0] not in (".gar", "build", "artifacts"):
            raise ValueError("Generated simulation hardware must be under .gar/, build/ or artifacts/")
        overrides = inside(self.root, settings["simulation_overrides"])
        from hardware_profiles import generate
        return generate(self.hardware, overrides, output)

    def build(self, *, native=False):
        self.validate()
        if self.kind == "platformio":
            if native:
                raise ValueError("Use the Product simulator hook for host application builds")
            from embedded import build
            return build(self)
        output = inside(self.root, self.data["build"]["directory"], exists=False)
        output.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(GAR_TOOLS_ROOT=str(self.components["tools"]), GAR_BUILD_DIR=str(output))
        if native:
            env.update(CC=env.get("CC", "gcc"), CXX=env.get("CXX", "g++"))
        else:
            toolchain = self.profile["toolchain"]
            if "sdk_env" in toolchain:
                sdk = env.get(toolchain["sdk_env"])
                if not sdk:
                    raise ValueError(f"Set {toolchain['sdk_env']} to an installed SDK; SDK bytes are external")
                prefix = inside(sdk, toolchain["prefix"] + "-gcc").as_posix().removesuffix("-gcc")
                env.update(CC=prefix + "-gcc", CXX=prefix + "-g++")
                header = inside(sdk, toolchain["gpio_uapi"])
                include = output / "uapi/linux"
                include.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(header, include / "gpio.h")
                env["CPATH"] = str(include.parent) + (os.pathsep + env["CPATH"] if env.get("CPATH") else "")
            else:
                env.update(CC=env.get("CC", toolchain["cc"]), CXX=env.get("CXX", toolchain["cxx"]))
        script = inside(self.components["application"], self.data["build"]["script"])
        subprocess.run(["sh", str(script)], env=env, cwd=self.root, check=True)
        for name in self.data["build"]["outputs"]:
            if not (output / name).is_file():
                raise ValueError(f"Build output missing: {name}")
        # A native build verifies sources, but must never become a physical payload.
        (output / "composition-build.json").write_text(json.dumps({
            "mode": "native" if native else "target", "board": self.board["id"],
            "profile": self.data["board_profile"], "architecture": self.profile["architecture"],
        }) + "\n", encoding="utf-8")
        return output
