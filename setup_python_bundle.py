"""
Setup script to download and prepare Python embeddable package for bundling
This creates a standalone Python environment with all required packages for the importer
"""

import os
import sys
import urllib.request
import zipfile
import ssl
import subprocess
import shutil
from pathlib import Path

# Python version to bundle (matches your current Python)
PYTHON_VERSION = "3.11.9"
PYTHON_VERSION_SHORT = "311"

# Create SSL context that works in VM environments
def create_ssl_context():
    """Create SSL context with fallback for certificate verification issues"""
    try:
        return ssl.create_default_context()
    except:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

def download_file(url, destination):
    """Download a file with progress indication"""
    print(f"Downloading from {url}...")
    ssl_context = create_ssl_context()
    
    try:
        with urllib.request.urlopen(url, context=ssl_context, timeout=120) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            with open(destination, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\rProgress: {percent:.1f}%", end='')
            print()  # New line after download
        return True
    except Exception as e:
        print(f"Error downloading: {e}")
        return False

def setup_python_embed():
    """Download and setup Python embeddable package"""
    
    # Paths
    script_dir = Path(__file__).parent
    embed_dir = script_dir / 'python-embed'
    temp_zip = script_dir / 'python-embed.zip'
    
    # Check if already exists
    if embed_dir.exists():
        print(f"Python embed directory already exists at {embed_dir}")
        response = input("Do you want to recreate it? (y/n): ").lower()
        if response != 'y':
            print("Using existing Python embed directory")
            return embed_dir
        print("Removing existing directory...")
        shutil.rmtree(embed_dir)
    
    print(f"Setting up Python {PYTHON_VERSION} embeddable package...")
    
    # Download Python embeddable package
    python_url = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
    
    if not download_file(python_url, temp_zip):
        print("Failed to download Python embeddable package")
        return None
    
    # Extract Python
    print("Extracting Python...")
    os.makedirs(embed_dir, exist_ok=True)
    with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
        zip_ref.extractall(embed_dir)
    
    # Clean up zip
    os.remove(temp_zip)
    print(f"✓ Extracted Python to {embed_dir}")
    
    # Modify python{version}._pth to enable site-packages
    pth_file = embed_dir / f'python{PYTHON_VERSION_SHORT}._pth'
    if pth_file.exists():
        print("Enabling site-packages in Python...")
        with open(pth_file, 'r') as f:
            content = f.read()
        
        # Uncomment the import site line
        content = content.replace('#import site', 'import site')
        # Add Lib/site-packages if not present
        if 'Lib\\site-packages' not in content:
            content += '\nLib\\site-packages\n'
        
        with open(pth_file, 'w') as f:
            f.write(content)
        print("✓ Enabled site-packages")
    
    # Download get-pip.py
    print("Downloading get-pip.py...")
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_path = embed_dir / 'get-pip.py'
    
    if not download_file(get_pip_url, get_pip_path):
        print("Failed to download get-pip.py")
        return None
    
    # Install pip
    print("Installing pip...")
    python_exe = embed_dir / 'python.exe'
    result = subprocess.run([str(python_exe), str(get_pip_path)], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error installing pip: {result.stderr}")
        return None
    print("✓ Installed pip")
    
    # Clean up get-pip.py
    get_pip_path.unlink()
    
    # Install required packages for the importer
    print("\nInstalling required packages for CS2 Importer...")
    packages = [
        'vmfpy',           # For VMF parsing
        'vpk',             # For VPK file handling
        'Pillow',          # For image processing
        'vdf',             # For VDF parsing
        'keyvalues3',      # For KV3 format
    ]
    
    for package in packages:
        print(f"  Installing {package}...")
        result = subprocess.run([str(python_exe), '-m', 'pip', 'install', package],
                              capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    Warning: Failed to install {package}")
            print(f"    {result.stderr}")
        else:
            print(f"    ✓ Installed {package}")
    
    print("\n" + "="*60)
    print("✓ Python embeddable package setup complete!")
    print(f"Location: {embed_dir}")
    print("="*60)
    
    return embed_dir

def verify_setup(embed_dir):
    """Verify the Python installation works"""
    if not embed_dir or not embed_dir.exists():
        return False
    
    print("\nVerifying installation...")
    python_exe = embed_dir / 'python.exe'
    
    # Test Python execution
    result = subprocess.run([str(python_exe), '--version'], 
                          capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Python version: {result.stdout.strip()}")
    else:
        print("✗ Python execution failed")
        return False
    
    # Test pip
    result = subprocess.run([str(python_exe), '-m', 'pip', '--version'],
                          capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Pip installed: {result.stdout.strip()}")
    else:
        print("✗ Pip not working")
        return False
    
    # List installed packages
    print("\nInstalled packages:")
    result = subprocess.run([str(python_exe), '-m', 'pip', 'list'],
                          capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    
    return True

if __name__ == '__main__':
    print("="*60)
    print("CS2KZ Mapping Tools - Python Bundle Setup")
    print("="*60)
    print()
    
    embed_dir = setup_python_embed()
    
    if embed_dir and verify_setup(embed_dir):
        print("\n✓ Setup successful! You can now build the executable.")
        print("\nNext steps:")
        print("  1. Run: pyinstaller CS2KZMappingTools_TEST.spec")
        print("  2. Test the built executable")
    else:
        print("\n✗ Setup failed. Please check the errors above.")
        sys.exit(1)
