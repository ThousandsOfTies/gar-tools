"""Small Product hook entry point; all commands are offline unless install is explicit."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from product import Product


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("describe")
    commands.add_parser("validate")
    build = commands.add_parser("build")
    build.add_argument("--native", action="store_true")
    package = commands.add_parser("package")
    package.add_argument("--output", default="artifacts/board-composition-target")
    args = parser.parse_args()
    product = Product(args.root).validate()
    if args.action in ("describe", "validate"):
        print(json.dumps(product.describe(), ensure_ascii=False, indent=2))
    elif args.action == "build":
        print(product.build(native=args.native))
    elif args.action == "package":
        from package import package_product
        print(package_product(product, args.output))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f"Composition error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
