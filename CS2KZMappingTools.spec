# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules
import os
import sys
import site

block_cipher = None

# Compute pathex including project root and any site-packages entries so PyInstaller
# can find installed packages like imgui when building in CI environments.
site_paths = []
try:
    site_paths = site.getsitepackages()
except Exception:
    # Fallback: include any sys.path entries that look like site-packages
    site_paths = [p for p in sys.path if 'site-packages' in (p or '')]
pathex = [os.path.abspath('.')] + site_paths

# Collect all imgui, glfw, and OpenGL modules
imgui_datas, imgui_binaries, imgui_hiddenimports = collect_all('imgui')
glfw_datas, glfw_binaries, glfw_hiddenimports = collect_all('glfw')
opengl_datas, opengl_binaries, opengl_hiddenimports = collect_all('OpenGL')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=imgui_binaries + glfw_binaries + opengl_binaries,
    datas=[
        ('icons', 'icons'),
        ('chars', 'chars'),
        ('scripts', 'scripts'),
        ('utils', 'utils'),
    ] + imgui_datas + glfw_datas + opengl_datas,
    hiddenimports=[
        'PIL._tkinter_finder',
        'OpenGL.GL',
        'OpenGL.GLU',
        'OpenGL.GLUT',
        'OpenGL.platform',
        'OpenGL.arrays',
        'OpenGL.arrays.arraydatatype',
        'OpenGL.accelerate',
        'glfw',
        'glfw._glfw',
        'imgui',
        'imgui.core',
        'imgui.internal',
        'imgui.integrations',
        'imgui.integrations.glfw',
        'vdf',
        'psutil',
        'requests',
        'vtf2img',
        'winreg',
        'tkinter',
        'tkinter.filedialog',
        'webbrowser',
        'urllib.request',
        'zipfile',
        'io',
        'traceback',
        'tempfile',
        're',
        'shutil',
        'subprocess',
        'os',
        'sys',
        'ctypes',
        'ctypes.wintypes',
        '_ctypes',
    ] + imgui_hiddenimports + glfw_hiddenimports + opengl_hiddenimports + collect_submodules('imgui') + collect_submodules('glfw'),
    hookspath=['.',],  # Look for hook files in current directory
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='CS2KZMappingTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX compression - can cause issues with some modules
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Enable console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/icon.ico',
)
