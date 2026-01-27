# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for RASEN orchestrator."""

from PyInstaller.utils.hooks import collect_data_files
import sys
from pathlib import Path

project_root = Path(SPECPATH)

# Collect data files
# Prompts are now bundled in the rasen package (src/rasen/prompts/)
datas = [
    (str(project_root / 'src' / 'rasen' / 'prompts'), 'rasen/prompts'),  # Include prompt templates
]

# Collect package data
datas += collect_data_files('rasen')

a = Analysis(
    ['src/rasen/cli.py'],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'rasen',
        'rasen.cli',
        'rasen.config',
        'rasen.models',
        'rasen.exceptions',
        'rasen.logging',
        'rasen.claude_runner',
        'rasen.prompts',
        'rasen.events',
        'rasen.git',
        'rasen.validation',
        'rasen.loop',
        'rasen.review',
        'rasen.qa',
        'rasen.stores',
        'rasen.stores.plan_store',
        'rasen.stores.recovery_store',
        'rasen.stores.memory_store',
        'rasen.stores.status_store',
        'rasen.stores._atomic',
        'click',
        'pydantic',
        'yaml',
        'rich',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'mypy',
        'ruff',
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='rasen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
