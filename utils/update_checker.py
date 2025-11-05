"""
Update checker for CS2KZ-Mapping-Tools
Checks GitHub Releases for new versions and manages update process
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import tempfile
import shutil
import subprocess
from datetime import datetime, timedelta

class UpdateChecker:
    def __init__(self):
        """Initialize the update checker"""
        self.github_repo = "jakkekz/CS2KZ-Mapping-Tools"
        self.github_releases_api = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
        self.current_version = self._get_current_version()
        self.last_check_time = None
        self.update_available = False
        self.latest_download_url = None
        self.latest_version = None
        
    def _get_current_version(self):
        """Get the current version from the executable or a version file"""
        try:
            # Try to read from version file
            if hasattr(sys, '_MEIPASS'):
                # Running as PyInstaller executable
                exe_path = sys.executable
                return os.path.getmtime(exe_path)
            else:
                # Running as script - use main.py timestamp
                main_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
                return os.path.getmtime(main_py)
        except Exception as e:
            print(f"Error getting current version: {e}")
            return 0
    
    def should_check_for_updates(self):
        """Check if enough time has passed since last check (5 minutes)"""
        if self.last_check_time is None:
            return True
        
        time_since_check = time.time() - self.last_check_time
        return time_since_check >= 300  # 5 minutes in seconds
    
    def check_for_updates(self):
        """Check GitHub Releases for new versions"""
        if not self.should_check_for_updates():
            return self.update_available
        
        self.last_check_time = time.time()
        
        try:
            # Get the latest release from GitHub
            req = urllib.request.Request(
                self.github_releases_api,
                headers={'Accept': 'application/vnd.github.v3+json'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                # Get release information
                published_at = data.get('published_at', '')
                if not published_at:
                    return False
                
                # Parse release timestamp
                release_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                release_timestamp = release_time.timestamp()
                
                # Compare with current version
                if release_timestamp > self.current_version:
                    # Find the .exe asset
                    assets = data.get('assets', [])
                    for asset in assets:
                        name = asset.get('name', '')
                        if name.endswith('.exe') and 'CS2KZ-Mapping-Tools' in name:
                            self.update_available = True
                            self.latest_download_url = asset.get('browser_download_url')
                            self.latest_version = release_timestamp
                            return True
                
        except urllib.error.URLError as e:
            print(f"Network error checking for updates: {e}")
        except Exception as e:
            print(f"Error checking for updates: {e}")
        
        self.update_available = False
        return False
    
    def download_and_install_update(self):
        """Download the latest version and replace the current executable"""
        if not self.update_available or not self.latest_download_url:
            return False
        
        try:
            # Get temp directory
            temp_dir = os.path.join(tempfile.gettempdir(), ".cs2kz-mapping-tools")
            update_dir = os.path.join(temp_dir, "update")
            
            # Create update directory
            os.makedirs(update_dir, exist_ok=True)
            
            # Download the new executable
            new_exe_path = os.path.join(update_dir, "CS2KZ-Mapping-Tools-new.exe")
            
            print(f"Downloading update from {self.latest_download_url}...")
            urllib.request.urlretrieve(self.latest_download_url, new_exe_path)
            
            if not os.path.exists(new_exe_path):
                print("Failed to download update")
                return False
            
            # Clear temp folder (except settings and Source2Viewer)
            self._clear_temp_folder(temp_dir)
            
            # Get current executable path
            if hasattr(sys, '_MEIPASS'):
                current_exe = sys.executable
            else:
                # Running as script - can't update
                print("Update only works for compiled executable")
                return False
            
            # Create a batch script to replace the executable
            batch_script = os.path.join(update_dir, "update.bat")
            with open(batch_script, 'w') as f:
                f.write('@echo off\n')
                f.write('echo Updating CS2KZ-Mapping-Tools...\n')
                f.write('timeout /t 2 /nobreak > nul\n')  # Wait for main app to close
                f.write(f'move /y "{new_exe_path}" "{current_exe}"\n')
                f.write(f'start "" "{current_exe}"\n')
                f.write(f'del "%~f0"\n')  # Delete the batch script itself
            
            # Run the batch script and exit
            subprocess.Popen(['cmd', '/c', batch_script], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            
            return True
            
        except Exception as e:
            print(f"Error during update: {e}")
            return False
    
    def _clear_temp_folder(self, temp_dir):
        """Clear the temp folder but preserve settings"""
        try:
            if not os.path.exists(temp_dir):
                return
            
            # Files/folders to preserve
            preserve = ['settings.json', 'Source2Viewer-win.exe', 'update']
            
            for item in os.listdir(temp_dir):
                if item in preserve:
                    continue
                
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    print(f"Error removing {item_path}: {e}")
                    
        except Exception as e:
            print(f"Error clearing temp folder: {e}")
    
    def restart_application(self):
        """Restart the application after update"""
        try:
            if hasattr(sys, '_MEIPASS'):
                # Running as executable - exit and let batch script restart
                sys.exit(0)
            else:
                # Running as script
                python = sys.executable
                subprocess.Popen([python] + sys.argv)
                sys.exit(0)
            
        except Exception as e:
            print(f"Error restarting application: {e}")
            return False
