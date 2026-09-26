# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — builds a different artifact per platform:

- macOS:   dist/YtLyrics.app  (then repacked to .dmg in CI)
- Windows: dist/YtLyrics.exe  (onefile, then wrapped into .msi in CI)
- Linux:   dist/YtLyrics      (single binary, packed as .AppImage in CI)
"""
from __future__ import annotations

import sys

from PyInstaller.utils.hooks import collect_all

# make sure static-ffmpeg binaries are on disk before bundling
try:
    from static_ffmpeg import run as _srun

    _srun.get_or_fetch_platform_executables_else_raise()
except Exception:  # noqa: BLE001 - runtime will fetch on first run
    pass

block_cipher = None

extra_datas: list = []
extra_bins: list = []
extra_his: list = []
for _pkg in (
    "yt_dlp",
    "static_ffmpeg",
    "faster_whisper",
    "ctranslate2",
    "googleapiclient",
    "google_auth_oauthlib",
    "google.oauth2",
    "requests_oauthlib",
    "google_auth_httplib2",
):
    try:
        _d, _b, _h = collect_all(_pkg)
    except Exception:  # noqa: BLE001 - optional subpackage
        continue
    extra_datas += _d
    extra_bins += _b
    extra_his += _h

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=extra_bins,
    datas=extra_datas,
    hiddenimports=extra_his,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="YtLyrics",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name="YtLyrics",
    )
    app = BUNDLE(
        coll,
        name="YtLyrics.app",
        icon="packaging/icons/YtLyrics.icns",
        bundle_identifier="com.vi3ecode.ytlyrics",
        version="1.0.0",
        info_plist={
            "CFBundleName": "YtLyrics",
            "CFBundleDisplayName": "YtLyrics",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.music",
            "NSHumanReadableCopyright": "Vi3ecode.com",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="YtLyrics",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        icon=(
            "packaging/icons/YtLyrics.ico"
            if sys.platform == "win32"
            else None
        ),
    )
