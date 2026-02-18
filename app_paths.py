from __future__ import annotations

import sys
from pathlib import Path


def app_base_dir() -> Path:
    """
    Returns the directory where runtime config files should live.

    - PyInstaller exe: alongside the exe
    - Source run: project root (parent of shiftgen package)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

