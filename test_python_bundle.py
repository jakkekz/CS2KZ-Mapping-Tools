# Test script to verify Python bundle after setup
import os
import sys
from pathlib import Path

def test_python_bundle():
    """Test that python-embed directory is set up correctly"""
    
    script_dir = Path(__file__).parent
    embed_dir = script_dir / 'python-embed'
    
    print("Testing Python bundle setup...")
    print(f"Looking for: {embed_dir}")
    print()
    
    # Check directory exists
    if not embed_dir.exists():
        print("✗ FAIL: python-embed directory not found")
        print("  Run: python setup_python_bundle.py")
        return False
    
    print("✓ python-embed directory exists")
    
    # Check Python executable
    python_exe = embed_dir / 'python.exe'
    if not python_exe.exists():
        print("✗ FAIL: python.exe not found")
        return False
    
    print("✓ python.exe exists")
    
    # Check required packages
    required_packages = ['vmfpy', 'vpk', 'PIL', 'vdf', 'keyvalues3', 'pip']
    site_packages = embed_dir / 'Lib' / 'site-packages'
    
    if not site_packages.exists():
        print("✗ FAIL: site-packages directory not found")
        return False
    
    print("✓ site-packages directory exists")
    
    missing = []
    for package in required_packages:
        # Check if package directory or .dist-info exists
        package_found = False
        for item in site_packages.iterdir():
            if item.name.lower().startswith(package.lower()):
                package_found = True
                break
        
        if package_found:
            print(f"  ✓ {package}")
        else:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print()
        print(f"✗ FAIL: Missing packages: {', '.join(missing)}")
        print("  Run: python setup_python_bundle.py")
        return False
    
    # Calculate size
    total_size = sum(f.stat().st_size for f in embed_dir.rglob('*') if f.is_file())
    size_mb = total_size / (1024 * 1024)
    
    print()
    print(f"Bundle size: {size_mb:.1f} MB")
    print()
    print("✓ SUCCESS: Python bundle is ready for packaging")
    print()
    print("Next step: Run build_complete.bat or pyinstaller CS2KZMappingTools_TEST.spec")
    
    return True

if __name__ == '__main__':
    success = test_python_bundle()
    sys.exit(0 if success else 1)
