from __future__ import annotations

import sys
from pathlib import Path


def app_base_dir() -> Path:
    """
    Directory where runtime config files should live.

    - PyInstaller exe: alongside the exe
    - Source run: alongside the entry script (e.g. app.py)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    # 1) If invoked via a script path, trust its directory.
    try:
        script = Path(sys.argv[0]).resolve()
        if script.is_file():
            return script.parent
    except Exception:
        pass

    # 2) Fall back to the directory above the local `shiftgen/` package.
    try:
        return Path(__file__).resolve().parent.parent
    except Exception:
        pass

    # 3) Last resort.
    return Path.cwd().resolve()


def find_runtime_file(filename: str) -> Path | None:
    """
    Locate a runtime-config file by checking a few likely directories.
    This protects against odd cwd/launch conditions and "submodule-like" layouts.
    """
    seen: set[Path] = set()
    candidates = []

    # Common cases
    try:
        candidates.append(app_base_dir())
    except Exception:
        pass
    try:
        candidates.append(Path.cwd().resolve())
    except Exception:
        pass
    try:
        candidates.append(Path(__file__).resolve().parent.parent)
    except Exception:
        pass

    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        p = base / filename
        if p.exists():
            return p

    return None
