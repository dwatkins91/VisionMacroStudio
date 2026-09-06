# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_root = Path(SPECPATH)
# The entry script runs at the bundle root, so its runtime assets belong in
# _internal/assets. app.main also accepts the older app/assets location.
datas = [(str(project_root / "app" / "assets"), "assets")]
binaries = []
hiddenimports = [
    "mss.windows",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
]

# Ultralytics loads model families and tasks dynamically. Collecting its package
# data and submodules prevents an apparently successful build from failing only
# when a model is opened. Torch's official PyInstaller hook handles its DLLs.
for package in ("ultralytics", "torchvision"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

for distribution in ("ultralytics", "torch", "torchvision", "opencv-python", "PyYAML"):
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VisionMacroStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "app" / "assets" / "vision_macro_eye.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VisionMacroStudio",
)
