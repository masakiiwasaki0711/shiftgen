# PyInstaller spec to reliably bundle native deps like ortools.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

project_root = Path(__file__).resolve().parent

hiddenimports = []
datas = []
binaries = []

for pkg in ("ortools", "openpyxl", "jpholiday"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# ortools often uses dynamic imports and native binaries.
hiddenimports += collect_submodules("ortools")

# Ensure our package is always bundled.
hiddenimports += collect_submodules("shiftgen")

a = Analysis(
    ["app.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="shiftgen",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed
)
