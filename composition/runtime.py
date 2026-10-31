"""Install only the Product-selected, checksum-verified Node runtime locally."""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import tarfile
from pathlib import Path

from package import identity_script
from product import Product


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    product = Product(args.root).validate()
    if os.geteuid() != 0:
        raise ValueError("Runtime installation requires root")
    subprocess.run(["sh", "-ec", identity_script(product.profile)], check=True)
    node = product.data["runtime"]
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != node["sha256"]:
        raise ValueError("Runtime archive SHA256 mismatch")
    directory = node["archive"].removesuffix(".tar.xz")
    target = Path(product.data["deployment"]["root"])
    with tarfile.open(args.archive, "r:xz") as archive:
        for relative in ("bin/node", "LICENSE"):
            member = archive.getmember(directory + "/" + relative)
            if not member.isfile():
                raise ValueError("Runtime archive member must be a regular file")
            output = target / directory / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("wb") as stream:
                stream.write(archive.extractfile(member).read())
            output.chmod(0o755 if relative == "bin/node" else 0o644)
    link = target / "node"
    if link.exists() and not link.is_symlink():
        raise ValueError("Runtime link path is occupied by a directory")
    if link.is_symlink():
        link.unlink()
    link.symlink_to(directory, target_is_directory=True)
    subprocess.run([str(link / "bin/node"), "--version"], check=True)


if __name__ == "__main__":
    main()
