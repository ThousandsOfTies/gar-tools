#!/usr/bin/env python3
"""Run the M5Status Tiny Renode smoke test with a verified sample ELF."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Sequence


RENODE_VERSION = "1.16.1"
RENODE_VERSION_PATTERN = re.compile(
    rf"\bRenode(?:, version| v)\s*{re.escape(RENODE_VERSION)}(?:\.|[\s(]|$)"
)
SAMPLE_ELF_NAME = "xtensa-sample-controller-zephyr-hello-world.elf"
SAMPLE_ELF_URL = (
    "https://dl.antmicro.com/projects/renode/"
    "xtensa-sample-controller-zephyr-hello-world.elf-s_293544-"
    "4be60f8a3891e70c30e1e8a471df4ad12ab08144"
)
SAMPLE_ELF_SHA256 = "6b4e9193b68fd6459de648560094d1d1a96f82a654f8a1f90629e5fb3a843079"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the pinned M5Status Tiny Renode firmware smoke test."
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="run the Robot assertion instead of the console smoke run",
    )
    parser.add_argument(
        "--elf",
        type=Path,
        help="use an existing sample ELF after verifying its checksum",
    )
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(DOWNLOAD_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_elf(path: Path) -> None:
    actual = sha256(path)
    if actual != SAMPLE_ELF_SHA256:
        raise RuntimeError(
            f"Renode sample ELF checksum mismatch: expected {SAMPLE_ELF_SHA256}, "
            f"got {actual}"
        )


def download_elf(destination: Path) -> None:
    request = urllib.request.Request(
        SAMPLE_ELF_URL,
        headers={"User-Agent": "gar-tools-renode-smoke/1"},
    )
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=30) as response:
        with destination.open("wb") as output:
            while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                output.write(chunk)
                digest.update(chunk)

    actual = digest.hexdigest()
    if actual != SAMPLE_ELF_SHA256:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Downloaded Renode sample ELF checksum mismatch: "
            f"expected {SAMPLE_ELF_SHA256}, got {actual}"
        )


def has_required_renode_version(version_output: str) -> bool:
    return RENODE_VERSION_PATTERN.search(version_output) is not None


def require_renode_version() -> str:
    renode_executable = shutil.which("renode")
    if renode_executable is None:
        raise RuntimeError("Renode is not installed or `renode` is not on PATH")

    result = subprocess.run(
        [renode_executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    version_output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0 or not has_required_renode_version(version_output):
        raise RuntimeError(
            f"Renode {RENODE_VERSION} is required; `renode --version` returned:\n"
            f"{version_output.strip()}"
        )
    return renode_executable


def find_renode_test_executable(renode_executable: str) -> str:
    """Prefer the renode-test launcher shipped beside the checked Renode."""

    renode_path = Path(renode_executable)
    candidates = [renode_path.with_name("renode-test")]
    resolved_candidate = renode_path.resolve().with_name("renode-test")
    if resolved_candidate != candidates[0]:
        candidates.append(resolved_candidate)

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    fallback = shutil.which("renode-test")
    if fallback is not None:
        return fallback
    raise RuntimeError("`renode-test` is not installed or is not on PATH")


def run_smoke(
    elf_path: Path,
    working_directory: Path,
    renode_executable: str = "renode",
) -> int:
    script_path = working_directory / "run.resc"
    shutil.copy2(Path(__file__).with_name("run.resc"), script_path)
    commands = (
        f"$m5status_tiny_elf=@{elf_path.as_posix()}; "
        f"include @{script_path.as_posix()}; start; quit"
    )
    result = subprocess.run(
        [renode_executable, "--console", "--disable-xwt", "--execute", commands],
        check=False,
        cwd=working_directory,
    )
    return result.returncode


def run_robot_test(
    elf_path: Path,
    working_directory: Path,
    renode_test_executable: str = "renode-test",
) -> int:
    test_path = Path(__file__).with_name("m5status-tiny.robot").resolve()
    result = subprocess.run(
        [
            renode_test_executable,
            "--variable",
            f"ELF:{elf_path.as_posix()}",
            str(test_path),
        ],
        check=False,
        cwd=working_directory,
    )
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    renode_executable = require_renode_version()
    renode_test_executable = (
        find_renode_test_executable(renode_executable) if args.test else None
    )

    with tempfile.TemporaryDirectory(prefix="gar-renode-m5status-") as temporary:
        working_directory = Path(temporary)
        if args.elf is None:
            elf_path = working_directory / SAMPLE_ELF_NAME
            download_elf(elf_path)
        else:
            supplied_elf = args.elf.expanduser().resolve()
            if not supplied_elf.is_file():
                raise RuntimeError(f"Renode sample ELF not found: {supplied_elf}")
            verify_elf(supplied_elf)
            elf_path = working_directory / SAMPLE_ELF_NAME
            shutil.copy2(supplied_elf, elf_path)

        if args.test:
            assert renode_test_executable is not None
            return run_robot_test(
                elf_path,
                working_directory,
                renode_test_executable,
            )
        return run_smoke(elf_path, working_directory, renode_executable)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
