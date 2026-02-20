# PyInstaller spec to reliably bundle native deps like ortools.

from PyInstaller.utils.hooks import collect_all, collect_submodules

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
        # If package isn't installed in the build env, PyInstaller will fail later anyway.
        pass

hiddenimports += collect_submodules("ortools")

a = Analysis(
    ["app.py"],
    pathex=[],
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

