# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for SanGir Automations desktop backend.

Build: pyinstaller build/sangir-backend.spec
Output: dist/sangir-backend/ (one-dir bundle with all deps)
"""

import os
from PyInstaller.building.datastruct import Tree

block_cipher = None

a = Analysis(
    ["desktop_backend.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Web UI (Jinja2 templates, static assets)
        ("app/web/templates", "app/web/templates"),
        ("app/web/static", "app/web/static"),
        # Schema YAMLs (column mapping)
        ("fcmr_core/schemas", "fcmr_core/schemas"),
        # Reference data (PIN master, etc.)
        ("fcmr_core/reference", "fcmr_core/reference"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.server",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websocket.auto",
        "uvicorn.protocols.websocket.wsproto_impl",
        # Data processing
        "duckdb",
        "polars",
        "pyarrow",
        # Excel
        "openpyxl",
        # Config
        "pydantic_settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[
        # Exclude dev/test dependencies
        "pytest",
        "black",
        "ruff",
        "pytest_asyncio",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sangir-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Show console window (remove for GUI-only)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
