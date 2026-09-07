# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Trify CSV Merger (macOS .app + Windows .exe).

Build with the helper scripts, or directly:
    pyinstaller build/CSVMerger.spec --noconfirm
"""

import sys
from pathlib import Path

# `SPECPATH` is injected by PyInstaller; the project root is one level up.
ROOT = Path(SPECPATH).resolve().parent
ASSETS = ROOT / "assets"

APP_NAME = "Trify CSV Merger"
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

icon = None
if IS_MAC and (ASSETS / "icon.icns").exists():
    icon = str(ASSETS / "icon.icns")
elif IS_WIN and (ASSETS / "icon.ico").exists():
    icon = str(ASSETS / "icon.ico")

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    # PGPy pulls `imghdr` (restored by the standard-imghdr backport on 3.13+).
    hiddenimports=["imghdr"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["PIL", "PyInstaller", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_MAC:
    # onedir + .app bundle (the mode PyInstaller recommends on macOS).
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False, strip=False, upx=False,
        console=False, disable_windowed_traceback=False,
        icon=icon,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas,
        strip=False, upx=False, name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier="pl.trify.csvmerger",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": "2.0.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.productivity",
        },
    )
else:
    # Windows / Linux: a single self-contained executable, easy to hand off.
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name=APP_NAME,
        debug=False, bootloader_ignore_signals=False,
        strip=False, upx=False, runtime_tmpdir=None,
        console=False, disable_windowed_traceback=False,
        icon=icon,
    )
