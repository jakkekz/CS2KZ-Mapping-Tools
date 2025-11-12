# Building CS2KZ Mapping Tools with Bundled Python

This document explains how to build a standalone executable that includes Python and all dependencies, so users don't need Python installed on their system.

## Problem

The CS2 Map Importer tool needs to run Python scripts (`import_map_community_jakke.py`) but users may not have Python installed. This causes the tool to fail with "Python not found" errors.

## Solution

We bundle an embedded Python distribution with all required packages directly into the executable. This makes the tool completely standalone.

## Build Process

### Quick Build (Recommended)

Simply run:
```batch
build_complete.bat
```

This script will:
1. Download Python 3.11.9 embeddable package (~10MB)
2. Install pip and required packages (vmfpy, vpk, Pillow, vdf, keyvalues3)
3. Build the executable with PyInstaller
4. Include the Python bundle in the final .exe

### Manual Build Steps

If you prefer to run steps manually:

1. **Setup Python Bundle**
   ```batch
   python setup_python_bundle.py
   ```
   This creates a `python-embed` folder with Python 3.11.9 and all dependencies.

2. **Build Executable**
   ```batch
   pyinstaller CS2KZMappingTools_TEST.spec --clean
   ```

## What Gets Bundled

The final executable includes:

- **Bundled Python** (`python-embed/`)
  - Python 3.11.9 embeddable package
  - pip package manager
  - Required packages:
    - `vmfpy` - VMF file parsing
    - `vpk` - VPK archive handling
    - `Pillow` - Image processing
    - `vdf` - Valve Data Format parsing
    - `keyvalues3` - KeyValues3 format support

- **Application Code**
  - All scripts from `scripts/` folder
  - UI resources (icons, fonts, chars)
  - Utility modules

## How It Works

1. When the importer runs, it looks for `python-embed/python.exe` (using `resource_path()` for PyInstaller compatibility)
2. If found, it uses the bundled Python (no system Python needed)
3. If not found, it falls back to system Python (with error if not installed)

## File Size

- Python embeddable package: ~10MB
- Installed packages: ~15MB
- Total addition to exe size: ~25MB

This is acceptable for a standalone tool that doesn't require users to install Python.

## Testing

After building, test on a clean system (VM without Python installed):

1. Copy `dist\CS2KZMappingTools_TEST.exe` to test system
2. Run the executable
3. Try using the CS2 Map Importer tool
4. Verify it works without Python installed

## Troubleshooting

### "python-embed directory not found" during build
- Run `python setup_python_bundle.py` first
- Or run `build_complete.bat` which does this automatically

### Import errors in built executable
- Make sure all required packages are in `setup_python_bundle.py`
- Check that packages installed successfully (look for ✓ marks in setup output)
- Rebuild with `pyinstaller CS2KZMappingTools_TEST.spec --clean`

### Large executable size
- This is normal - bundling Python adds ~25MB
- Alternative: require users to install Python (not recommended for end users)

## Updating Python Version

To update the bundled Python version:

1. Edit `setup_python_bundle.py`
2. Change `PYTHON_VERSION = "3.11.9"` to desired version
3. Delete existing `python-embed` folder
4. Run `python setup_python_bundle.py` again

## Adding New Package Dependencies

If you add new Python package requirements to the importer:

1. Edit `setup_python_bundle.py`
2. Add package to the `packages` list in `setup_python_embed()` function
3. Delete `python-embed` folder
4. Run `python setup_python_bundle.py` again
5. Rebuild the executable

## SSL Certificate Issues

The setup script includes SSL context fallback for VM environments where certificate verification fails. This is the same fix applied to the main application for downloading resources.
