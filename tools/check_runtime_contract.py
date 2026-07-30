#!/usr/bin/env python3
"""Validate gar-tools target manifests with GaplessAgentRuntime's contract."""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

RUNTIME_MARKER = Path("scripts/gar_lib/target/manifest.py")


class ContractCheckError(RuntimeError):
    """The Runtime repository or a cross-repository contract is invalid."""


def find_runtime_root(tools_root: Path, configured: str | Path | None = None) -> Path:
    """Find a Runtime checkout configured explicitly, as a sibling, or nested."""

    if configured:
        candidates = [Path(configured).expanduser()]
    else:
        candidates = [
            tools_root.parent / "GaplessAgentRuntime",
            tools_root / "GaplessAgentRuntime",
        ]

    checked: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        checked.append(resolved)
        if (resolved / RUNTIME_MARKER).is_file():
            return resolved

    locations = ", ".join(str(path) for path in checked)
    raise ContractCheckError(
        "GaplessAgentRuntime checkout not found. "
        f"Checked: {locations}. Set GAR_RUNTIME_ROOT to its repository root."
    )


def manifest_layout_issues(
    tools_root: Path,
    manifests: Sequence[Any],
    backend_ids_by_category: Mapping[str, set[str]],
) -> list[str]:
    """Return gar-tools layout errors not covered by Runtime's parser."""

    issues: list[str] = []
    manifests_by_id: dict[str, Any] = {}
    for manifest in manifests:
        if manifest.id in manifests_by_id:
            issues.append(
                f"Runtime discovery returned duplicate target id {manifest.id!r}"
            )
        manifests_by_id[manifest.id] = manifest

    paths = sorted((tools_root / "targets").glob("*/target.json"))
    if not paths:
        issues.append(f"{tools_root / 'targets'}: no target manifests found")
    declared_ids: set[str] = set()

    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            issues.append(f"{path}: cannot read JSON: {error}")
            continue
        if not isinstance(payload, dict):
            issues.append(f"{path}: JSON root must be an object")
            continue

        target_id = payload.get("id")
        if not isinstance(target_id, str) or not target_id:
            issues.append(f"{path}: id must be a non-empty string")
            continue
        if target_id in declared_ids:
            issues.append(f"{path}: duplicate target id {target_id!r}")
        declared_ids.add(target_id)

        folder_name = path.parent.name
        if target_id != folder_name:
            issues.append(f"{path}: id {target_id!r} must match folder {folder_name!r}")

        manifest = manifests_by_id.get(target_id)
        if manifest is None:
            issues.append(
                f"{path}: Runtime discovery did not return target {target_id!r}"
            )
            continue

        expected_tools_root = path.parent.relative_to(tools_root).as_posix()
        if manifest.tools_root != expected_tools_root:
            issues.append(
                f"{path}: toolsRoot {manifest.tools_root!r} must be {expected_tools_root!r}"
            )

        actual_categories = set(manifest.default_backends)
        expected_categories = set(backend_ids_by_category)
        missing_categories = expected_categories - actual_categories
        if missing_categories:
            missing = ", ".join(sorted(missing_categories))
            issues.append(f"{path}: defaultBackends is missing categories: {missing}")
        unexpected_categories = actual_categories - expected_categories
        if unexpected_categories:
            unexpected = ", ".join(sorted(unexpected_categories))
            issues.append(
                f"{path}: defaultBackends has unknown categories: {unexpected}"
            )

        for category_id, backend_id in manifest.default_backends.items():
            available = backend_ids_by_category.get(category_id)
            if available is not None and backend_id not in available:
                candidates = ", ".join(sorted(available))
                issues.append(
                    f"{path}: defaultBackends.{category_id} has unknown backend "
                    f"{backend_id!r}; expected one of: {candidates}"
                )

    undisclosed = set(manifests_by_id) - declared_ids
    if undisclosed:
        target_ids = ", ".join(sorted(undisclosed))
        issues.append(
            f"Runtime discovery returned targets without manifests: {target_ids}"
        )

    return issues


def check_runtime_contract(tools_root: Path, runtime_root: Path) -> None:
    """Load Runtime's registry and parser, then validate all target manifests."""

    sys.path.insert(0, str(runtime_root))
    os.environ["GAR_TOOLS_ROOT"] = str(tools_root)
    os.environ["GAR_TOOLS_TARGETS"] = str(tools_root / "targets")

    try:
        from scripts.gar_lib.environments.discovery import discover_environments
        from scripts.gar_lib.target.manifest import discover_target_manifests

        environments = discover_environments()
        if inspect.signature(discover_target_manifests).parameters:
            manifests = discover_target_manifests(environments)
        else:
            manifests = discover_target_manifests()
    except Exception as error:
        raise ContractCheckError(str(error)) from error

    backends: dict[str, set[str]] = {}
    for environment in environments:
        backends.setdefault(environment.category_id, set()).add(
            environment.environment_id
        )

    issues = manifest_layout_issues(tools_root, manifests, backends)
    if issues:
        details = "\n".join(f"  - {issue}" for issue in issues)
        raise ContractCheckError(f"gar-tools target contract failed:\n{details}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-root",
        help="GaplessAgentRuntime repository root (defaults to GAR_RUNTIME_ROOT, sibling, or nested checkout)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    tools_root = Path(__file__).resolve().parents[1]
    configured = args.runtime_root or os.environ.get("GAR_RUNTIME_ROOT")
    try:
        runtime_root = find_runtime_root(tools_root, configured)
        check_runtime_contract(tools_root, runtime_root)
    except ContractCheckError as error:
        print(f"runtime contract check failed: {error}", file=sys.stderr)
        return 1

    manifest_count = len(list((tools_root / "targets").glob("*/target.json")))
    print(f"runtime contract check passed: {manifest_count} target manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
