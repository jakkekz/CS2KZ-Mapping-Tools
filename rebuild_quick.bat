@echo off
REM Quick rebuild script - skips Python bundle setup if it already exists

echo ============================================================
echo CS2KZ Mapping Tools - Quick Rebuild
echo ============================================================
echo.

REM Check if python-embed already exists
if not exist "python-embed\" (
    echo Python bundle not found - running full setup...
    echo.
    python setup_python_bundle.py
    if %errorlevel% neq 0 (
        echo ERROR: Python bundle setup failed
        pause
        exit /b 1
    )
) else (
    echo ✓ Python bundle already exists, skipping setup
)

echo.
echo Building executable with PyInstaller...
echo ============================================================
pyinstaller CS2KZMappingTools_TEST.spec --clean
if %errorlevel% neq 0 (
    echo.
    echo ERROR: PyInstaller build failed
    pause
    exit /b 1
)

echo.
echo ============================================================
echo ✓ Rebuild complete!
echo ============================================================
echo.
echo Executable: dist\CS2KZMappingTools_TEST.exe
echo.
echo Changes included in this build:
echo   - SSL certificate verification fix for VM environments
echo   - Bundled Python for importer tool
echo.
pause
