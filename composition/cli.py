"""Small Product hook entry point; all commands are offline unless install is explicit."""
from __future__ import annotations

import argparse
import json
import subprocess
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
    commands.add_parser("prepare")
    artifact = commands.add_parser("artifact")
    artifact.add_argument("--kind", choices=["target_app", "sim_app", "sim_runtime"], required=True)
    artifact.add_argument("--clean", action="store_true")
    contract = commands.add_parser("hardware-contract")
    contract.add_argument("--capabilities", type=Path, required=True)
    contract.add_argument("--output", default=".gar/hardware-contract")
    component = commands.add_parser("component")
    component.add_argument("role", choices=["application", "tools", "board"])
    hardware = commands.add_parser("hardware")
    hardware.add_argument("--environment", choices=["physical", "simulation"], default="simulation")
    environment = commands.add_parser("environment")
    environment.add_argument("--environment", choices=["physical", "simulation"], default="physical")
    environment.add_argument("--format", choices=["json", "systemd"], default="json")
    build = commands.add_parser("build")
    build.add_argument("--native", action="store_true")
    package = commands.add_parser("package")
    package.add_argument("--output", default="artifacts/board-composition-target")
    package.add_argument("--replace", action="store_true", help="Replace generated Python staging output")
    clean = commands.add_parser("clean")
    clean.add_argument("--output", default="artifacts/from-codespace")
    args = parser.parse_args()
    product = Product(args.root).validate()
    if args.action in ("describe", "validate"):
        print(json.dumps(product.describe(), ensure_ascii=False, indent=2))
    elif args.action == "build":
        print(product.build(native=args.native))
    elif args.action == "prepare":
        print(product.prepare())
    elif args.action == "artifact":
        from artifact import run
        print(run(product, args.kind, clean=args.clean))
    elif args.action == "hardware-contract":
        from hardware_contract import generate
        print(generate(product, args.capabilities, args.output))
    elif args.action == "component":
        print(product.components[args.role])
    elif args.action == "hardware":
        print(product.hardware_for(args.environment))
    elif args.action == "environment":
        if product.data['build'].get('backend') != 'python':
            raise ValueError('Environment rendering requires a declared Python launch configuration')
        from python_app import environment
        values = environment(product, args.environment)
        if args.format == 'json':
            print(json.dumps(values, indent=2))
        else:
            for key, value in values.items():
                assignment = (key + '=' + value).replace('%', '%%')
                if any(character.isspace() or character in '\\"' for character in assignment):
                    assignment = json.dumps(assignment)
                print('Environment=' + assignment)
    elif args.action == "package":
        if product.data['build'].get('backend') in ('python', 'planned'):
            from python_app import package
            print(package(product, args.output, replace=args.replace))
            return
        if args.replace:
            raise ValueError('Replacing immutable native packages is not supported')
        if product.kind != "linux":
            raise ValueError("Use the Product target artifact hook for firmware packaging")
        from package import package_product
        print(package_product(product, args.output))
    elif args.action == "clean":
        if product.data['build'].get('backend') != 'python':
            raise ValueError('Generated package cleaning requires the Python backend')
        from python_app import clean
        clean(product, args.output)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, SyntaxError, TypeError, AttributeError, subprocess.CalledProcessError) as error:
        print(f"Composition error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
