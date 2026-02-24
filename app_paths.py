from __future__ import annotations

import sys
from pathlib import Path


def app_base_dir() -> Path:
    """
    Directory where runtime config files should live.

    - PyInstaller exe: alongside the exe
    - Source run: alongside the entry script (e.g. app.py)

    This avoids relying on the current working directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    # If invoked via an explicit script path, trust its directory.
    try:
        script = Path(sys.argv[0]).resolve()
        if script.is_file():
            return script.parent
    except Exception:
        pass

    # Fallback: this file lives next to the entry script in source layout.
    return Path(__file__).resolve().parent
