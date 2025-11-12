@echo off
REM CS2KZ Mapping Tools - Complete Build Script
REM This script sets up Python bundle and builds the executable

echo ============================================================
echo CS2KZ Mapping Tools - Build Script
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Step 1: Setting up Python embeddable package...
echo ============================================================
python setup_python_bundle.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to setup Python bundle
    echo Please check the error messages above
    pause
    exit /b 1
)

echo.
echo Step 2: Building executable with PyInstaller...
echo ============================================================
pyinstaller CS2KZMappingTools_TEST.spec --clean
if %errorlevel% neq 0 (
    echo.
    echo ERROR: PyInstaller build failed
    echo Please check the error messages above
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Build completed successfully!
echo ============================================================
echo.
echo Executable location: dist\CS2KZMappingTools_TEST.exe
echo.
echo The executable now includes:
echo   - Bundled Python (no Python installation required on target system)
echo   - All required packages (vmfpy, vpk, Pillow, vdf, keyvalues3)
echo   - All scripts and resources
echo.
echo You can now distribute the executable to users without Python installed.
echo.
pause
