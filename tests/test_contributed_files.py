"""First-line safety filter for contributed strategy files in strategies/.

Not a sandbox: every pull request is also reviewed by a person. This catches the
obvious cases (file, network or process access) before review.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "strategies"
FILES = sorted(p for p in ROOT.glob("*.py") if not p.name.startswith("_"))

ALLOWED_MODULES = {"fengan.strategies", "math", "statistics", "typing", "dataclasses", "__future__"}
FORBIDDEN_NAMES = {"open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars",
                   "getattr", "setattr", "delattr", "input", "breakpoint"}


def _module_ok(name: str) -> bool:
    return any(name == m or name.startswith(m + ".") for m in ALLOWED_MODULES)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_strategy_file_only_uses_safe_imports_and_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert _module_ok(alias.name), f"{path.name}: import {alias.name} is not allowed"
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and _module_ok(node.module or ""), \
                f"{path.name}: from {node.module} import ... is not allowed"
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_NAMES, f"{path.name}: use of {node.id} is not allowed"
        elif isinstance(node, ast.Attribute):
            assert not node.attr.startswith("__"), f"{path.name}: dunder attribute {node.attr} is not allowed"


def test_example_file_exists():
    assert (ROOT / "three_red_days.py").exists()
