from __future__ import annotations

import ast
from pathlib import Path


def python_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def imported_modules(path: Path, package_root: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_import_from(path, package_root, node)
            if module:
                modules.append(module)
    return modules


def import_violations(
    source_root: Path,
    package_root: Path,
    blocked_modules: dict[str, str],
) -> list[str]:
    issues: list[str] = []
    for path in python_files(source_root):
        for module in imported_modules(path, package_root):
            boundary = _blocked_boundary(module, blocked_modules)
            if boundary is None:
                continue
            rel = path.relative_to(package_root).as_posix()
            issues.append(f"{rel}: imports {module} ({boundary})")
    return sorted(issues)


def text_marker_violations(
    source_root: Path,
    package_root: Path,
    blocked_markers: dict[str, str],
) -> list[str]:
    issues: list[str] = []
    for path in python_files(source_root):
        text = path.read_text(encoding="utf-8")
        for marker, boundary in blocked_markers.items():
            if marker in text:
                rel = path.relative_to(package_root).as_posix()
                issues.append(f"{rel}: contains {marker} ({boundary})")
    return sorted(issues)


def _resolve_import_from(path: Path, package_root: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    try:
        relative = path.relative_to(package_root).with_suffix("")
    except ValueError:
        return node.module

    package_parts = list(relative.parts[:-1])
    if node.level > 1:
        package_parts = package_parts[: -(node.level - 1)]
    module_parts = node.module.split(".") if node.module else []
    resolved = [*package_parts, *module_parts]
    return ".".join(part for part in resolved if part) or None


def _blocked_boundary(module: str, blocked_modules: dict[str, str]) -> str | None:
    for prefix, boundary in blocked_modules.items():
        if module == prefix or module.startswith(prefix + "."):
            return boundary
    return None
