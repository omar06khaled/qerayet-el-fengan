"""Load user strategy files.

Every `*.py` file in a strategy folder is imported once at startup; each
`@strategy(...)` inside registers itself. A file that fails to import is
reported in LOAD_ERRORS instead of crashing the app.

Folders searched, in order:
  1. Each path in SAHM_STRATEGY_DIRS (separated by ; on Windows, : elsewhere)
  2. ./strategies in the current working directory
  3. strategies/ at the project root (next to pyproject.toml)

Strategy files are Python and run with your permissions. Only load files you
wrote or have read.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from . import base

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def strategy_dirs() -> list[Path]:
    dirs = [Path(p) for p in os.getenv("SAHM_STRATEGY_DIRS", "").split(os.pathsep) if p.strip()]
    dirs += [Path.cwd() / "strategies", _PROJECT_ROOT / "strategies"]
    seen, out = set(), []
    for d in dirs:
        r = d.resolve()
        if r not in seen and r.is_dir():
            seen.add(r)
            out.append(r)
    return out


def load_user_strategies() -> None:
    for folder in strategy_dirs():
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            load_file(path)


def load_file(path: Path) -> None:
    module_name = f"sahm_user_strategy_{path.stem}"
    if module_name in sys.modules:
        return
    before = set(base.REGISTRY)
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError("not a Python module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:  # report, never crash the app
        sys.modules.pop(module_name, None)
        for sid in set(base.REGISTRY) - before:
            base.REGISTRY.pop(sid, None)
        base.LOAD_ERRORS.append({"file": path.name, "error": f"{type(e).__name__}: {e}"})
        return
    for sid in set(base.REGISTRY) - before:
        base.REGISTRY[sid].source = f"your file: {path.name}"
