"""
Update checker for CS2KZ-Mapping-Tools
Checks GitHub Releases for new versions and manages update process!!
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
        self.last_check_time = None
        self.update_available = False
        self.latest_download_url = None
        self.latest_version = None
        self.latest_version_tag = None
        self.latest_version_date = None
        self.current_version_date = None
        self.current_version = self._get_current_version()
        
    def _get_current_version(self):
        """Get the current version from the executable or a version file"""
        try:
            # Try to read from version file
            if hasattr(sys, '_MEIPASS'):
                # Running as PyInstaller executable
                exe_path = sys.executable
                timestamp = os.path.getmtime(exe_path)
                # Store as UTC datetime for consistency with GitHub API
                self.current_version_date = datetime.fromtimestamp(timestamp)
                
                # Detect if running console version
                exe_name = os.path.basename(exe_path).lower()
                self.is_console_version = 'console' in exe_name
                
                print(f"[Update] Running as executable: {exe_path}")
                print(f"[Update] Console version detected: {self.is_console_version}")
                print(f"[Update] Executable timestamp (UTC): {timestamp}")
                print(f"[Update] Executable date (local): {self.current_version_date}")
                return timestamp
            else:
                # Running as script - use main.py timestamp
                main_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
                timestamp = os.path.getmtime(main_py)
                # Store as UTC datetime for consistency with GitHub API
                self.current_version_date = datetime.fromtimestamp(timestamp)
                self.is_console_version = False  # Default for script
                print(f"[Update] Running as script: {main_py}")
                print(f"[Update] Script timestamp (UTC): {timestamp}")
                print(f"[Update] Script date (local): {self.current_version_date}")
                return timestamp
        except Exception as e:
            print(f"[Update] Error getting current version: {e}")
            self.is_console_version = False
            return 0
    
    def should_check_for_updates(self):
        """Check if enough time has passed since last check (X minutes)"""
        if self.last_check_time is None:
            return True
        
        time_since_check = time.time() - self.last_check_time
        return time_since_check >= 150  # 2.5 minutes in seconds
    
    def check_for_updates(self):
        """Check GitHub Releases for new versions"""
        if not self.should_check_for_updates():
            print(f"[Update] Skipping check - last checked {time.time() - self.last_check_time:.0f}s ago")
            return self.update_available
        
        self.last_check_time = time.time()
        print(f"[Update] Checking for updates from GitHub Releases...")
        print(f"[Update] Current version timestamp: {self.current_version}")
        
        try:
            # Get the latest release from GitHub
            req = urllib.request.Request(
                self.github_releases_api,
                headers={'Accept': 'application/vnd.github.v3+json'}
            )
            
            print(f"[Update] Fetching: {self.github_releases_api}")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                # Get release information
                published_at = data.get('published_at', '')
                release_tag = data.get('tag_name', 'unknown')
                print(f"[Update] Latest release: {release_tag} published at {published_at}")
                
                if not published_at:
                    print("[Update] No published_at field in release")
                    return False
                
                # Parse release timestamp
                release_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                release_timestamp = release_time.timestamp()
                print(f"[Update] Release timestamp: {release_timestamp}")
                
                # Compare with current version
                if release_timestamp > self.current_version:
                    print(f"[Update] Release is newer! ({release_timestamp} > {self.current_version})")
                    # Find the correct .exe asset based on current version type
                    assets = data.get('assets', [])
                    print(f"[Update] Found {len(assets)} assets")
                    
                    target_asset_name = None
                    for asset in assets:
                        name = asset.get('name', '')
                        print(f"[Update] Asset: {name}")
                        # Look for ZIP files instead of EXE (new onedir format)
                        if name.endswith('.zip') and 'CS2KZ' in name and 'MappingTools' in name:
                            # Check if this matches the current version type
                            is_console_asset = 'console' in name.lower()
                            
                            if self.is_console_version == is_console_asset:
                                target_asset_name = name
                                self.update_available = True
                                self.latest_download_url = asset.get('browser_download_url')
                                self.latest_version = release_timestamp
                                self.latest_version_tag = release_tag
                                self.latest_version_date = release_time
                                print(f"[Update] ✓ Found matching version: {name} (console: {is_console_asset})")
                                print(f"[Update] Download URL: {self.latest_download_url}")
                                return True
                    
                    if not target_asset_name:
                        version_type = "console" if self.is_console_version else "windowed"
                        print(f"[Update] No matching {version_type} version found in assets")
                else:
                    print(f"[Update] Release is not newer ({release_timestamp} <= {self.current_version})")
                
        except urllib.error.URLError as e:
            print(f"[Update] Network error: {e}")
        except Exception as e:
            print(f"[Update] Error: {e}")
        
        self.update_available = False
        print("[Update] No update available")
        return False
    
    def download_and_install_update(self):
        """Download the latest version ZIP and prepare for extraction"""
        if not self.update_available or not self.latest_download_url:
            print("[Update] No update available or no download URL")
            return False
        
        try:
            import zipfile
            print(f"[Update] Starting update process...")
            
            # Get temp directory
            temp_dir = os.path.join(tempfile.gettempdir(), ".cs2kz-mapping-tools")
            update_dir = os.path.join(temp_dir, "update")
            
            # Create update directory
            os.makedirs(update_dir, exist_ok=True)
            print(f"[Update] Update directory: {update_dir}")
            
            # Download the new ZIP
            zip_path = os.path.join(update_dir, "CS2KZ-Mapping-Tools-new.zip")
            
            print(f"[Update] Downloading from {self.latest_download_url}...")
            urllib.request.urlretrieve(self.latest_download_url, zip_path)
            print(f"[Update] Downloaded to {zip_path}")
            
            if not os.path.exists(zip_path):
                print("[Update] Failed to download update - file doesn't exist")
                return False
            
            file_size = os.path.getsize(zip_path)
            print(f"[Update] Downloaded file size: {file_size} bytes")
            
            # Extract ZIP to temp location
            extract_dir = os.path.join(update_dir, "extracted")
            if os.path.exists(extract_dir):
                import shutil
                shutil.rmtree(extract_dir)
            
            print(f"[Update] Extracting ZIP...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            print(f"[Update] Extracted to {extract_dir}")
            
            # Get current installation directory (parent of _internal)
            if hasattr(sys, '_MEIPASS'):
                current_exe = sys.executable
                install_dir = os.path.dirname(current_exe)
                print(f"[Update] Current executable: {current_exe}")
                print(f"[Update] Installation directory: {install_dir}")
            else:
                # Running as script - can't update
                print("[Update] Running as script - update only works for compiled executable")
                return False
            
            # Find the extracted folder (it should be the only folder in extract_dir)
            extracted_folders = [f for f in os.listdir(extract_dir) if os.path.isdir(os.path.join(extract_dir, f))]
            if not extracted_folders:
                print("[Update] ERROR: No folder found in extracted ZIP")
                return False
            
            new_version_folder = os.path.join(extract_dir, extracted_folders[0])
            new_exe_path = os.path.join(new_version_folder, os.path.basename(current_exe))
            
            if not os.path.exists(new_exe_path):
                print(f"[Update] ERROR: New executable not found at {new_exe_path}")
                return False
            
            print(f"[Update] New version folder: {new_version_folder}")
            print(f"[Update] New executable: {new_exe_path}")
            
            # Create a batch script to replace the folder
            batch_script = os.path.join(update_dir, "update.bat")
            print(f"[Update] Creating batch script: {batch_script}")
            with open(batch_script, 'w') as f:
                f.write('@echo off\n')
                f.write('echo CS2KZ Mapping Tools Updater\n')
                f.write('echo =============================\n')
                f.write('echo.\n')
                f.write('echo Waiting for application to close...\n')
                f.write('timeout /t 3 /nobreak > nul\n')
                f.write('echo.\n')
                f.write('echo Updating application...\n')
                f.write('echo.\n')
                
                # Save settings.json if it exists
                settings_backup = os.path.join(update_dir, 'settings_backup.json')
                settings_file = os.path.join(install_dir, 'settings.json')
                f.write(f'if exist "{settings_file}" (\n')
                f.write(f'    echo Backing up settings...\n')
                f.write(f'    copy /y "{settings_file}" "{settings_backup}" > nul\n')
                f.write(f')\n')
                f.write('echo.\n')
                
                # Delete old installation (except a few files)
                f.write(f'echo Removing old version...\n')
                f.write(f'cd /d "{install_dir}"\n')
                f.write(f'for %%F in (*) do (\n')
                f.write(f'    if not "%%F"=="settings.json" (\n')
                f.write(f'        del /f /q "%%F" 2>nul\n')
                f.write(f'    )\n')
                f.write(f')\n')
                f.write(f'for /d %%D in (*) do (\n')
                f.write(f'    rd /s /q "%%D" 2>nul\n')
                f.write(f')\n')
                f.write('echo.\n')
                
                # Copy new version
                f.write(f'echo Installing new version...\n')
                f.write(f'xcopy "{new_version_folder}\\*" "{install_dir}\\" /s /e /y /i > nul\n')
                f.write('if errorlevel 1 (\n')
                f.write('    echo ERROR: Failed to copy new version!\n')
                f.write('    pause\n')
                f.write('    exit /b 1\n')
                f.write(')\n')
                f.write('echo.\n')
                
                # Restore settings.json
                f.write(f'if exist "{settings_backup}" (\n')
                f.write(f'    echo Restoring settings...\n')
                f.write(f'    copy /y "{settings_backup}" "{settings_file}" > nul\n')
                f.write(f'    del /f /q "{settings_backup}" > nul\n')
                f.write(f')\n')
                f.write('echo.\n')
                
                # Start new version
                f.write('echo Update complete! Starting application...\n')
                f.write(f'cd /d "{install_dir}"\n')
                f.write(f'start "" "{os.path.basename(current_exe)}"\n')
                f.write('echo.\n')
                f.write('timeout /t 2 /nobreak > nul\n')
                
                # Cleanup
                f.write(f'rd /s /q "{update_dir}" 2>nul\n')
                f.write('del "%~f0"\n')
            
            print("[Update] Launching update script and exiting...")
            # Run the batch script
            subprocess.Popen(['cmd', '/c', batch_script], creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            # Force immediate exit
            print("[Update] Exiting application for update...")
            import os as _os
            _os._exit(0)  # Immediate exit without cleanup
            
        except Exception as e:
            print(f"[Update] Error during update: {e}")
            return False
    
    def _clear_temp_folder(self, temp_dir):
        """Clear the temp folder but preserve settings and Source2Viewer"""
        try:
            if not os.path.exists(temp_dir):
                return
            
            # Files/folders to preserve (include both possible S2V names)
            preserve = ['settings.json', 'Source2Viewer-win.exe', 'Source2Viewer.exe', 'update']
            
            print(f"[Update] Clearing temp folder (preserving: {', '.join(preserve)})")
            
            for item in os.listdir(temp_dir):
                if item in preserve:
                    print(f"[Update] Preserving: {item}")
                    continue
                
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        print(f"[Update] Removed file: {item}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        print(f"[Update] Removed directory: {item}")
                except Exception as e:
                    print(f"[Update] Warning: Could not remove {item}: {e}")
                    
        except Exception as e:
            print(f"[Update] Error clearing temp folder: {e}")
    
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
