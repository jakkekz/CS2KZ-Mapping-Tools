"""
PyImGui version of CS2KZ Mapping Tools
Full-featured version with all capabilities from the original!!
"""

import imgui
import glfw
from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
from PIL import Image
import os
import sys
import subprocess
import psutil
import shutil
import threading
import tempfile
from scripts.settings_manager import SettingsManager
from utils.update_checker import UpdateChecker

# Helper function for PyInstaller to find bundled files
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_python_executable():
    """Get the correct Python executable to use"""
    # Check if running as PyInstaller exe
    if getattr(sys, 'frozen', False):
        # Running from PyInstaller exe - use python from PATH
        return 'python'
    else:
        # Running from normal Python - use current interpreter
        return sys.executable

# Window configuration
WINDOW_WIDTH = 259  # Fixed width for 2 columns (old non-compact): 14 + 112 + 7 + 112 + 14 = 259
WINDOW_WIDTH_NON_COMPACT = 828  # Width for non-compact: 20% wider than original 690px
WINDOW_WIDTH_COMPACT = 240  # Width for single column: increased for checkmark space
CUSTOM_TITLE_BAR_HEIGHT = 30  # Custom title bar height
MENU_BAR_HEIGHT = 0
TOP_PADDING = 0  # Padding above buttons - customize this value
BUTTON_SIZE = 112  # Old button size (unused now)
BUTTON_SIZE_NON_COMPACT = 140  # Height for non-compact mode (70% of 200)
BUTTON_SIZE_NON_COMPACT_WIDTH = 260  # Width for non-compact mode (fits 3 columns in 828px window)
BUTTON_SIZE_COMPACT_WIDTH = 212  # Wider button for compact mode (240 - 14 - 14 = 212)
BUTTON_SIZE_COMPACT_HEIGHT = 40  # Shorter button for compact mode
BUTTON_SPACING = 10  # Increased spacing for non-compact
BUTTON_SPACING_COMPACT = 7  # Original spacing for compact
ROW_HEIGHT = BUTTON_SIZE + BUTTON_SPACING  # Space for button + spacing between rows (old)
ROW_HEIGHT_NON_COMPACT = BUTTON_SIZE_NON_COMPACT + BUTTON_SPACING  # Button + spacing (no label box now)
ROW_HEIGHT_COMPACT = BUTTON_SIZE_COMPACT_HEIGHT + BUTTON_SPACING_COMPACT  # Space for compact buttons
BOTTOM_PADDING = 55  # Padding below buttons - compact mode uses this
BOTTOM_PADDING_NON_COMPACT = 45  # Padding for non-compact mode
WINDOW_TITLE = "CS2KZ Mapping Tools"


class ImGuiApp:
    def __init__(self):
        self.window = None
        self.impl = None
        
        # Initialize settings manager
        self.settings = SettingsManager()
        
        # Button visibility states from settings
        saved_visibility = self.settings.get_visible_buttons()
        self.button_visibility = {
            "dedicated_server": saved_visibility.get("dedicated_server", False),
            "insecure": saved_visibility.get("insecure", False),
            "listen": saved_visibility.get("listen", True),
            "mapping": saved_visibility.get("mapping", True),
            "source2viewer": saved_visibility.get("source2viewer", True),
            "cs2importer": saved_visibility.get("cs2importer", True),
            "skyboxconverter": saved_visibility.get("skyboxconverter", True),
            "vtf2png": saved_visibility.get("vtf2png", False),
            "loading_screen": saved_visibility.get("loading_screen", True),
            "point_worldtext": saved_visibility.get("point_worldtext", False),
            "sounds": saved_visibility.get("sounds", True)
        }
        
        # Button order from settings
        self.button_order = self.settings.get_button_order()
        
        # Settings from settings manager
        self.show_move_icons = self.settings.get('show_move_icons', False)
        self.auto_update_source2viewer = self.settings.get('auto_update_source2viewer', True)
        self.auto_update_metamod = self.settings.get('auto_update_metamod', True)
        self.auto_update_cs2kz = self.settings.get('auto_update_cs2kz', True)
        self.compact_mode = self.settings.get('compact_mode', False)  # Default to non-compact mode
        
        # Theme system - support both old and new format
        appearance = self.settings.get('appearance_mode', 'grey')
        # Convert old dark/light to new theme names
        if appearance == 'dark':
            appearance = 'grey'
        elif appearance == 'light':
            appearance = 'white'
        self.current_theme = appearance
        self.dark_mode = appearance not in ['white']  # For compatibility with existing code
        
        # Window opacity
        self.window_opacity = self.settings.get('window_opacity', 1.0)
        
        # Always on top
        self.always_on_top = self.settings.get('always_on_top', False)
        
        # Flag to track if window needs resize (deferred until menu closes)
        self.needs_window_resize = False
        
        # Button icons (texture IDs will be loaded here)
        self.button_icons = {}
        
        # Long-press drag and drop state
        self.dragging_button = None
        self.hover_target = None
        self.button_press_start_time = {}  # Track when each button was pressed
        self.button_press_start_pos = {}   # Track mouse position when pressed
        self.button_positions = {}         # Store button screen positions
        self.drag_threshold_time = 0.3     # Seconds to hold before drag starts
        self.drag_threshold_distance = 5   # Pixels to move before drag starts
        self.dragged_button_icon = None    # Store icon/label for dragged button
        self.dragged_button_label = None
        
        # Custom title bar drag state
        self.dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Window position
        self.window_pos = None
        
        # Current window height based on visible buttons
        self.current_window_height = self.calculate_window_height()
        
        # CS2 detection state
        self.cs2_client_running = False  # Client (insecure/listen/mapping)
        self.cs2_dedicated_running = False  # Dedicated server
        
        # Source2Viewer download state
        self.s2v_downloading = False
        
        # Cursor state
        self.current_cursor = None
        self.should_show_hand = False
        
        # Update checker
        self.update_checker = UpdateChecker()
        self.update_available = False
        self.last_update_check = 0
    
    def set_cursor(self, cursor_type):
        """Set the cursor if it's different from current"""
        if self.current_cursor != cursor_type:
            if cursor_type == "hand":
                glfw.set_cursor(self.window, self.hand_cursor)
            else:
                glfw.set_cursor(self.window, self.arrow_cursor)
            self.current_cursor = cursor_type
    
    def is_cs2_running(self):
        """Check if CS2 is running and return (client_running, dedicated_running)"""
        client_running = False
        dedicated_running = False
        
        try:
            # Much faster: iterate through all processes only once with minimal attributes
            for proc in psutil.process_iter(['name']):
                try:
                    name = proc.info['name']
                    if name:
                        name_lower = name.lower()
                        # Check for real cs2.exe
                        if name_lower == 'cs2.exe':
                            # Check command line to distinguish between client and dedicated server
                            try:
                                cmdline = proc.cmdline()
                                # Dedicated server has -dedicated in command line
                                if cmdline and any('-dedicated' in arg.lower() for arg in cmdline):
                                    dedicated_running = True
                                else:
                                    client_running = True
                            except (psutil.AccessDenied, psutil.NoSuchProcess):
                                # If we can't read cmdline, assume it's a client for safety
                                client_running = True
                        # Check for python processes (for fake_cs2.py testing)
                        elif 'python' in name_lower:
                            # Only check cmdline for python processes
                            cmdline = proc.cmdline()
                            if cmdline and any('fake_cs2.py' in arg.lower() for arg in cmdline):
                                client_running = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            pass
        
        return client_running, dedicated_running
    
    def check_s2v_download_status(self):
        """Check if Source2Viewer is currently downloading"""
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        download_flag = os.path.join(app_dir, '.s2v_downloading')
        return os.path.exists(download_flag)
    
    def check_for_updates(self):
        """Check for application updates from GitHub Actions"""
        try:
            # Auto-update temporarily disabled for onedir builds
            # Users should manually download new versions from GitHub Releases
            self.update_available = False
            # Check if update checker is available and check for updates
            # if self.update_checker:
            #     self.update_available = self.update_checker.check_for_updates()
        except Exception as e:
            print(f"Error checking for updates: {e}")
    
    def perform_update(self):
        """Download and install the latest update"""
        try:
            # Auto-update temporarily disabled for onedir builds
            # Open GitHub releases page for manual download
            import webbrowser
            webbrowser.open("https://github.com/jakkekz/CS2KZ-Mapping-Tools/releases/latest")
            # if self.update_checker and self.update_available:
            #     success = self.update_checker.download_and_install_update()
            #     if success:
            #         self.update_checker.restart_application()
        except Exception as e:
            print(f"Error performing update: {e}")
    
    def clear_settings(self):
        """Clear saved settings and reset to defaults"""
        import tempfile
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        settings_file = os.path.join(app_dir, 'settings.json')
        
        try:
            # Remove the settings file
            if os.path.exists(settings_file):
                os.remove(settings_file)
                print("Settings file removed")
            
            # Reset in-memory settings to defaults
            self.settings.settings = self.settings.default_settings.copy()
            self.settings.save_settings()
            
            # Reset app state to match defaults
            self.button_visibility = {
                "dedicated_server": False,
                "insecure": False,
                "listen": True,
                "mapping": True,
                "source2viewer": True,
                "cs2importer": True,
                "skyboxconverter": True,
                "vtf2png": False,
                "loading_screen": True,
                "point_worldtext": False,
                "sounds": True
            }
            self.button_order = ['mapping', 'listen', 'dedicated_server', 'insecure', 'source2viewer', 'cs2importer', 'skyboxconverter', 'loading_screen', 'point_worldtext', 'vtf2png', 'sounds']
            self.show_move_icons = False
            self.auto_update_source2viewer = True
            self.auto_update_metamod = True
            self.auto_update_cs2kz = True
            self.compact_mode = False  # Default to non-compact mode
            self.current_theme = 'grey'  # Default theme
            self.dark_mode = True
            self.window_opacity = 1.0
            self.always_on_top = False
            
            # Apply visual changes
            self.setup_style()
            glfw.set_window_opacity(self.window, self.window_opacity)
            glfw.set_window_attrib(self.window, glfw.FLOATING, glfw.FALSE)
            
            # Recalculate window size
            new_height = self.calculate_window_height()
            new_width = self.get_window_width()
            glfw.set_window_size(self.window, new_width, new_height)
            self.current_window_height = new_height
            
            print("Settings reset to defaults successfully")
        except Exception as e:
            print(f"Error clearing settings: {e}")
    
    def clear_version_cache(self):
        """Clear Metamod/CS2KZ version cache"""
        import tempfile
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        version_file = os.path.join(app_dir, 'cs2kz_versions.txt')
        
        try:
            if os.path.exists(version_file):
                os.remove(version_file)
                print("Version cache cleared successfully")
            else:
                print("No version cache found")
        except Exception as e:
            print(f"Error clearing version cache: {e}")
    
    def clear_temp_folder(self):
        """Clear temporary folder except Source2Viewer and settings"""
        import tempfile
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        
        # Files to keep (don't delete)
        keep_files = {'settings.json', 'Source2Viewer.exe', 'ValveResourceFormat.xml'}
        
        try:
            if os.path.exists(app_dir):
                # Remove all files and folders except protected files
                files_removed = 0
                folders_removed = 0
                
                for item in os.listdir(app_dir):
                    if item not in keep_files:
                        item_path = os.path.join(app_dir, item)
                        try:
                            if os.path.isfile(item_path):
                                os.remove(item_path)
                                files_removed += 1
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                                folders_removed += 1
                        except Exception as e:
                            print(f"Error removing {item}: {e}")
                
                print(f"Temp folder cleared: {files_removed} files and {folders_removed} folders removed")
            else:
                print("No temp folder found")
        except Exception as e:
            print(f"Error clearing temp folder: {e}")
    
    def clear_all_data(self):
        """Clear all saved data and caches (except Source2Viewer)"""
        import tempfile
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        
        # Files to keep (don't delete)
        keep_files = {'Source2Viewer.exe', 'ValveResourceFormat.xml'}
        
        try:
            # Remove files from app directory except Source2Viewer
            if os.path.exists(app_dir):
                files_removed = 0
                for filename in os.listdir(app_dir):
                    if filename not in keep_files:
                        file_path = os.path.join(app_dir, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                files_removed += 1
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                                files_removed += 1
                        except Exception as e:
                            print(f"Error removing {filename}: {e}")
                print(f"App data cleared: {files_removed} items removed")
            
            print("All data cleared successfully (Source2Viewer preserved)")
        except Exception as e:
            print(f"Error clearing all data: {e}")
    
    def remove_source2viewer(self):
        """Remove Source2Viewer from temp directory"""
        import tempfile
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        
        files_to_remove = ['Source2Viewer.exe', 'ValveResourceFormat.xml']
        
        try:
            files_removed = 0
            for filename in files_to_remove:
                file_path = os.path.join(app_dir, filename)
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        files_removed += 1
                        print(f"Removed: {filename}")
                    except Exception as e:
                        print(f"Error removing {filename}: {e}")
            
            if files_removed > 0:
                print(f"Source2Viewer removed successfully ({files_removed} files)")
            else:
                print("Source2Viewer not found")
        except Exception as e:
            print(f"Error removing Source2Viewer: {e}")
    
    def verify_game_files(self):
        """Restore all modified game files to original state from GitHub"""
        import winreg
        import vdf
        import urllib.request
        
        print("Starting game file verification...")
        
        try:
            # Get CS2 path using same method as other scripts
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            except FileNotFoundError:
                print("✗ Steam installation not found")
                return
            
            libraryfolders_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
            if not os.path.exists(libraryfolders_path):
                print("✗ Steam library folders not found")
                return
            
            with open(libraryfolders_path, 'r', encoding='utf-8') as file:
                library_data = vdf.load(file)
            
            cs2_library_path = None
            if 'libraryfolders' in library_data:
                for _, folder in library_data['libraryfolders'].items():
                    if 'apps' in folder and '730' in folder['apps']:
                        cs2_library_path = folder['path']
                        break
            
            if not cs2_library_path:
                print("✗ CS2 installation not found")
                return
            
            cs2_path = os.path.join(cs2_library_path, 'steamapps', 'common', 'Counter-Strike Global Offensive')
            
            if not os.path.exists(cs2_path):
                print(f"✗ CS2 path not found: {cs2_path}")
                return
            
            print(f"Found CS2 at: {cs2_path}")
            
            # Files to restore from GitHub
            BASE_URL = 'https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/refs/heads/master/'
            
            files_to_restore = [
                'game/csgo/gameinfo.gi',
                'game/csgo_core/gameinfo.gi',
                'game/bin/sdkenginetools.txt',
                'game/bin/assettypes_common.txt'
            ]
            
            files_restored = 0
            files_failed = 0
            
            for file_path in files_to_restore:
                url = BASE_URL + file_path
                full_path = os.path.join(cs2_path, file_path)
                
                try:
                    print(f"Downloading {file_path}...")
                    response = urllib.request.urlopen(url, timeout=10)
                    
                    if response.getcode() != 200:
                        print(f"✗ Failed to download {file_path} (HTTP {response.getcode()})")
                        files_failed += 1
                        continue
                    
                    content = response.read().decode('utf-8').replace('\n', '\r\n')
                    
                    # Create directory if needed
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    
                    # Write file
                    with open(full_path, 'wb') as f:
                        f.write(content.encode('utf-8'))
                    
                    print(f"✓ Restored {file_path}")
                    files_restored += 1
                    
                except Exception as e:
                    print(f"✗ Error restoring {file_path}: {e}")
                    files_failed += 1
            
            # Summary
            print(f"\nVerification complete:")
            print(f"  ✓ {files_restored} files restored")
            if files_failed > 0:
                print(f"  ✗ {files_failed} files failed")
            
            # Check for and restore vpk.signatures.old
            vpk_signatures_old = os.path.join(cs2_path, 'game', 'csgo', 'vpk.signatures.old')
            vpk_signatures = os.path.join(cs2_path, 'game', 'csgo', 'vpk.signatures')
            
            if os.path.exists(vpk_signatures_old):
                try:
                    # Remove existing vpk.signatures if it exists
                    if os.path.exists(vpk_signatures):
                        os.remove(vpk_signatures)
                    
                    # Rename vpk.signatures.old back to vpk.signatures
                    os.rename(vpk_signatures_old, vpk_signatures)
                    print(f"  ✓ Restored vpk.signatures from backup")
                    
                except Exception as e:
                    print(f"  ✗ Failed to restore vpk.signatures: {e}")
            
            print("\nGame files have been restored to their original state.")
            print("(Addons folder preserved)")
            
        except Exception as e:
            print(f"✗ Error during verification: {e}")
    
    def open_data_folder(self):
        """Open the data folder in Windows Explorer"""
        import tempfile
        import subprocess
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        
        try:
            # Create directory if it doesn't exist
            if not os.path.exists(app_dir):
                os.makedirs(app_dir, exist_ok=True)
            
            # Open in Windows Explorer
            subprocess.Popen(['explorer', app_dir])
            print(f"Opened data folder: {app_dir}")
        except Exception as e:
            print(f"Error opening data folder: {e}")
    
    def format_version(self, version_string):
        """Format version string to show only version and build number
        Example: 'Metamod: 2.0.0 (build 1367)' -> '2.0.0 (build 1367)'
        Example: 'mmsource-2.0.0-git1367-windows.zip' -> '2.0.0 (build 1367)'
        """
        if not version_string or version_string == 'Not installed':
            return version_string
        
        # Handle Metamod filename format: mmsource-2.0.0-git1367-windows.zip
        if version_string.startswith('mmsource-') and version_string.endswith('.zip'):
            # Extract version and build from filename
            import re
            match = re.match(r'mmsource-(\d+\.\d+\.\d+)-git(\d+)-.*\.zip', version_string)
            if match:
                version = match.group(1)
                build = match.group(2)
                return f"{version} (build {build})"
        
        # Strip prefix like "Metamod: " or "CS2KZ: "
        if ':' in version_string:
            version_string = version_string.split(':', 1)[1].strip()
        
        return version_string
    
    def get_button_tooltip(self, name):
        """Get tooltip text for a button"""
        import tempfile
        
        # Load version information for buttons that need it
        temp_dir = os.getenv('TEMP')
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        version_file = os.path.join(app_dir, 'cs2kz_versions.txt')
        versions = {}
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            versions[key] = value
            except:
                pass
        
        # Format version strings
        metamod_version = self.format_version(versions.get('metamod', 'Not installed'))
        cs2kz_version = self.format_version(versions.get('cs2kz', 'Not installed'))
        
        # Get Source2Viewer path
        s2v_path = os.path.join(app_dir, 'Source2Viewer.exe')
        
        tooltips = {
            "mapping": "Launches CS2 Hammer Editor with the latest Metamod, CS2KZ and Mapping API versions. (insecure)",
            
            "listen": "Launches CS2 with the latest Metamod and CS2KZ versions. (insecure)",
            
            "dedicated_server": "Launches a CS2 Dedicated Server with the latest Metamod, CS2KZ and Mapping API versions. (insecure)",
            
            "insecure": "Launches CS2 in insecure mode.",
            
            "source2viewer": f"Launches Source2Viewer with the latest dev build.\n(Updates may take some time)",

            "cs2importer": "Port CS:GO maps to CS2.\n\nInspired by:\nsarim-hk\nandreaskeller96",

            "skyboxconverter": "Automate the converting of cubemap skyboxes to a CS2 compatible format.",
            
            "loading_screen": "Automate the adding of Loading Screen Images, Map Icons and Descriptions.",
            
            "point_worldtext": "Create CS:GO style point_worldtext png images.",
            
            "vtf2png": "Convert CS:GO vtf files to png images.",
            
            "sounds": "Make adding custom sounds to CS2 easier."
        }
        
        return tooltips.get(name, "")
    
    def get_button_version(self, name):
        """Get version string for a button"""
        import tempfile
        
        temp_dir = os.getenv('TEMP')
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        version_file = os.path.join(app_dir, 'cs2kz_versions.txt')
        versions = {}
        
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            versions[key] = value
            except:
                pass
        
        # Return version info based on button type
        if name in ['mapping', 'listen', 'dedicated_server']:
            metamod = self.format_version(versions.get('metamod', 'N/A'))
            cs2kz = self.format_version(versions.get('cs2kz', 'N/A'))
            return [f"KZ: {cs2kz}", f"MM: {metamod}"]  # KZ first, then MM
        elif name == 'source2viewer':
            # Check if currently downloading
            if self.check_s2v_download_status():
                return ["wait..."] if self.compact_mode else ["Downloading..."]
            
            # Check if Source2Viewer.exe exists and is a valid file (not just empty/corrupt)
            s2v_path = os.path.join(app_dir, 'Source2Viewer.exe')
            
            # Check if file exists and has non-zero size
            if not os.path.exists(s2v_path) or os.path.getsize(s2v_path) < 1000:
                # Use shorter text in compact mode to prevent overlap
                return ["X"] if self.compact_mode else ["Not installed"]
            
            # Try to extract SHA from Product Version in executable
            local_sha = self.get_s2v_local_sha(s2v_path)
            if local_sha:
                # Check if it's the latest version
                is_latest = self.is_s2v_latest(local_sha, versions.get('source2viewer_latest', ''))
                # Return SHA with status indicator (will be color-coded in rendering)
                return [local_sha, "latest" if is_latest else "outdated"]
            
            # Fallback if can't read SHA
            return ["Unknown", "unknown"]
        
        return []
    
    def get_s2v_local_sha(self, exe_path):
        """Extract SHA from Source2Viewer.exe Product Version"""
        if not os.path.exists(exe_path):
            return None
        
        try:
            import win32api
            import re
            
            # Common locale paths to check for ProductVersion
            locale_paths = [
                '\\StringFileInfo\\040904B0\\ProductVersion',
                '\\StringFileInfo\\000004B0\\ProductVersion',
                '\\StringFileInfo\\040004B0\\ProductVersion'
            ]
            
            for path in locale_paths:
                try:
                    full_version_string = win32api.GetFileVersionInfo(exe_path, path)
                    # Look for pattern like "+1b65395" in "15.0.5033+1b65395"
                    match = re.search(r'\+([a-fA-F0-9]{7,8})', full_version_string)
                    if match:
                        return match.group(1).upper()
                except:
                    continue
        except:
            pass
        
        return None
    
    def is_s2v_latest(self, local_sha, remote_sha):
        """Check if local SHA matches the latest remote SHA"""
        if not local_sha or not remote_sha:
            return False
        
        # Compare first 7-8 characters (short SHA)
        local_short = local_sha[:8].upper()
        remote_short = remote_sha[:8].upper()
        
        return local_short == remote_short
    
    def calculate_window_height(self):
        """Calculate window height based on number of visible buttons"""
        visible_count = sum(1 for v in self.button_visibility.values() if v)
        if self.compact_mode:
            # Single column, one button per row
            num_rows = visible_count if visible_count > 0 else 1
            return CUSTOM_TITLE_BAR_HEIGHT + MENU_BAR_HEIGHT + TOP_PADDING + (num_rows * ROW_HEIGHT_COMPACT) + BOTTOM_PADDING
        else:
            # 3 columns for non-compact mode
            num_rows = (visible_count + 2) // 3 if visible_count > 0 else 1
            return CUSTOM_TITLE_BAR_HEIGHT + MENU_BAR_HEIGHT + TOP_PADDING + (num_rows * ROW_HEIGHT_NON_COMPACT) + BOTTOM_PADDING_NON_COMPACT
    
    def get_window_width(self):
        """Get window width based on compact mode"""
        return WINDOW_WIDTH_COMPACT if self.compact_mode else WINDOW_WIDTH_NON_COMPACT
    
    def swap_buttons(self, button1, button2):
        """Swap positions of two buttons in the order"""
        if button1 in self.button_order and button2 in self.button_order:
            idx1 = self.button_order.index(button1)
            idx2 = self.button_order.index(button2)
            self.button_order[idx1], self.button_order[idx2] = self.button_order[idx2], self.button_order[idx1]
            self.settings.set_button_order(self.button_order)
    
    def init_window(self):
        """Initialize GLFW window and ImGui"""
        if not glfw.init():
            print("Could not initialize GLFW")
            sys.exit(1)
        
        # Window hints
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)
        glfw.window_hint(glfw.DECORATED, glfw.FALSE)  # Remove window decorations for custom title bar
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)  # Start hidden to prevent black flash
        
        # Create window with calculated height
        window_width = self.get_window_width()
        self.window = glfw.create_window(window_width, self.current_window_height, WINDOW_TITLE, None, None)
        if not self.window:
            glfw.terminate()
            print("Could not create GLFW window")
            sys.exit(1)
        
        # Make window non-resizable
        glfw.set_window_attrib(self.window, glfw.RESIZABLE, glfw.FALSE)
        
        # Set always on top if enabled
        if self.always_on_top:
            glfw.set_window_attrib(self.window, glfw.FLOATING, glfw.TRUE)
        
        # Set window position from settings
        saved_pos = self.settings.get_window_position()
        if saved_pos:
            # Check if the saved position is on-screen
            # Get primary monitor to check bounds
            primary_monitor = glfw.get_primary_monitor()
            video_mode = glfw.get_video_mode(primary_monitor)
            screen_width = video_mode.size.width
            screen_height = video_mode.size.height
            
            # Only use saved position if it's at least partially on screen
            if (saved_pos[0] < screen_width - 50 and saved_pos[1] < screen_height - 50 and
                saved_pos[0] > -window_width + 50 and saved_pos[1] > -50):
                glfw.set_window_pos(self.window, saved_pos[0], saved_pos[1])
            else:
                # Center window if saved position is off-screen
                center_x = (screen_width - window_width) // 2
                center_y = (screen_height - self.current_window_height) // 2
                glfw.set_window_pos(self.window, center_x, center_y)
        else:
            # Center window on first launch
            primary_monitor = glfw.get_primary_monitor()
            video_mode = glfw.get_video_mode(primary_monitor)
            screen_width = video_mode.size.width
            screen_height = video_mode.size.height
            center_x = (screen_width - window_width) // 2
            center_y = (screen_height - self.current_window_height) // 2
            glfw.set_window_pos(self.window, center_x, center_y)
        
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)  # Enable vsync
        
        # Create hand cursor for clickable elements
        self.hand_cursor = glfw.create_standard_cursor(glfw.HAND_CURSOR)
        self.arrow_cursor = glfw.create_standard_cursor(glfw.ARROW_CURSOR)
        
        # Set window opacity
        glfw.set_window_opacity(self.window, self.window_opacity)
        
        # Set window icon
        icon_path = resource_path(os.path.join("icons", "hammerkz.ico"))
        if os.path.exists(icon_path):
            try:
                icon_img = Image.open(icon_path)
                if icon_img.mode != 'RGBA':
                    icon_img = icon_img.convert('RGBA')
                
                # Try to set window icon - GLFW format varies by version
                try:
                    # Try newer format with GLFWimage
                    from glfw import _GLFWimage
                    img_buffer = icon_img.tobytes()
                    img = _GLFWimage()
                    img.width = icon_img.width
                    img.height = icon_img.height
                    img.pixels = img_buffer
                    glfw.set_window_icon(self.window, 1, img)
                except:
                    # Try older list format
                    icon_data = icon_img.tobytes()
                    glfw.set_window_icon(self.window, 1, [[icon_img.width, icon_img.height, icon_data]])
            except Exception as e:
                # Silently fail - icon is nice to have but not critical
                pass
        
        # Setup ImGui
        imgui.create_context()
        
        # Load font based on theme
        io = imgui.get_io()
        
        # Store current theme for font selection
        current_theme = self.settings.get('appearance_mode', 'grey')
        self._last_theme_for_font = current_theme  # Initialize tracking
        
        # Always use Consolas font (Windows system font)
        consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
        if os.path.exists(consolas_path):
            io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
        else:
            # Fallback to Roboto if Consolas not found
            font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
            if os.path.exists(font_path):
                io.fonts.add_font_from_file_ttf(font_path, 13.0)
        
        self.impl = GlfwRenderer(self.window)
        
        # Create custom cursors
        self.arrow_cursor = glfw.create_standard_cursor(glfw.ARROW_CURSOR)
        self.hand_cursor = glfw.create_standard_cursor(glfw.HAND_CURSOR)
        
        # Setup ImGui style
        self.setup_style()
        
        # Load button icons
        self.load_icons()
    
    def setup_style(self):
        """Configure ImGui visual style"""
        style = imgui.get_style()
        io = imgui.get_io()
        
        # Check if theme changed and requires different font
        # Flag for reload but don't do it during frame rendering
        if hasattr(self, '_last_theme_for_font'):
            old_was_dracula = self._last_theme_for_font == 'dracula'
            new_is_dracula = self.current_theme == 'dracula'
            if old_was_dracula != new_is_dracula:
                self._needs_font_reload = True
        
        # Enable font with better rendering
        io.font_global_scale = 1.0
        
        # Theme definitions (background, menubar, button, button_hover, button_active, border, text)
        self.themes = {
            'grey': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.1, 0.1, 0.1, 1.0),
                'menubar_bg': (0.16, 0.16, 0.16, 1.0),
                'button': (0.29, 0.29, 0.29, 1.0),
                'button_hover': (0.35, 0.35, 0.35, 1.0),
                'button_active': (0.40, 0.40, 0.40, 1.0),
                'border': (0.40, 0.40, 0.40, 1.0),
                'text': (1.0, 1.0, 1.0, 1.0)
            },
            'black': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.0, 0.0, 0.0, 1.0),
                'menubar_bg': (0.05, 0.05, 0.05, 1.0),
                'button': (0.15, 0.15, 0.15, 1.0),
                'button_hover': (0.20, 0.20, 0.20, 1.0),
                'button_active': (0.25, 0.25, 0.25, 1.0),
                'border': (0.30, 0.30, 0.30, 1.0),
                'text': (1.0, 1.0, 1.0, 1.0)
            },
            'white': {
                'base': imgui.style_colors_light,
                'window_bg': (0.94, 0.94, 0.94, 1.0),
                'menubar_bg': (0.88, 0.88, 0.88, 1.0),
                'button': (0.75, 0.75, 0.75, 1.0),
                'button_hover': (0.70, 0.70, 0.70, 1.0),
                'button_active': (0.65, 0.65, 0.65, 1.0),
                'border': (0.60, 0.60, 0.60, 1.0),
                'text': (0.1, 0.1, 0.1, 1.0)
            },
            'pink': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.25, 0.12, 0.18, 1.0),
                'menubar_bg': (0.30, 0.15, 0.22, 1.0),
                'button': (0.55, 0.25, 0.40, 1.0),
                'button_hover': (0.65, 0.30, 0.48, 1.0),
                'button_active': (0.75, 0.35, 0.55, 1.0),
                'border': (0.80, 0.40, 0.60, 1.0),
                'text': (1.0, 0.95, 0.98, 1.0)
            },
            'orange': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.25, 0.15, 0.08, 1.0),
                'menubar_bg': (0.30, 0.18, 0.10, 1.0),
                'button': (0.60, 0.35, 0.15, 1.0),
                'button_hover': (0.70, 0.40, 0.18, 1.0),
                'button_active': (0.80, 0.45, 0.20, 1.0),
                'border': (0.85, 0.50, 0.25, 1.0),
                'text': (1.0, 0.98, 0.95, 1.0)
            },
            'blue': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.08, 0.12, 0.25, 1.0),
                'menubar_bg': (0.10, 0.15, 0.30, 1.0),
                'button': (0.20, 0.30, 0.60, 1.0),
                'button_hover': (0.25, 0.35, 0.70, 1.0),
                'button_active': (0.30, 0.40, 0.80, 1.0),
                'border': (0.35, 0.45, 0.85, 1.0),
                'text': (0.95, 0.98, 1.0, 1.0)
            },
            'red': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.25, 0.08, 0.08, 1.0),
                'menubar_bg': (0.30, 0.10, 0.10, 1.0),
                'button': (0.60, 0.20, 0.20, 1.0),
                'button_hover': (0.70, 0.25, 0.25, 1.0),
                'button_active': (0.80, 0.30, 0.30, 1.0),
                'border': (0.85, 0.35, 0.35, 1.0),
                'text': (1.0, 0.95, 0.95, 1.0)
            },
            'green': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.08, 0.18, 0.08, 1.0),
                'menubar_bg': (0.10, 0.22, 0.10, 1.0),
                'button': (0.20, 0.50, 0.20, 1.0),
                'button_hover': (0.25, 0.60, 0.25, 1.0),
                'button_active': (0.30, 0.70, 0.30, 1.0),
                'border': (0.35, 0.75, 0.35, 1.0),
                'text': (0.95, 1.0, 0.95, 1.0)
            },
            'yellow': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.5, 0.5, 0.00, 1.0),
                'menubar_bg': (0.5, 0.5, 0.00, 1.0),
                'button': (0.60, 0.55, 0.15, 1.0),
                'button_hover': (0.70, 0.65, 0.20, 1.0),
                'button_active': (0.80, 0.75, 0.25, 1.0),
                'border': (0.85, 0.80, 0.30, 1.0),
                'text': (1.0, 1.0, 0.90, 1.0)
            },
            'dracula': {
                'base': imgui.style_colors_dark,
                'window_bg': (0.157, 0.165, 0.212, 1.0),      # #282a36 (background)
                'menubar_bg': (0.173, 0.184, 0.235, 1.0),     # #2c2f3c (slightly lighter)
                'button': (0.271, 0.282, 0.353, 1.0),         # #44475a (current line)
                'button_hover': (0.506, 0.475, 0.702, 1.0),   # #bd93f9 (purple on hover)
                'button_active': (0.380, 0.345, 0.580, 1.0),  # #615894 (darker purple)
                'border': (0.380, 0.396, 0.486, 1.0),         # #61657c (subtle grey-purple)
                'text': (0.973, 0.973, 0.949, 1.0)            # #f8f8f2 (white text)
            }
        }
        
        # Get current theme or default to grey
        theme = self.themes.get(self.current_theme, self.themes['grey'])
        
        # Apply base style
        theme['base']()
        
        # Apply theme colors
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = theme['window_bg']
        style.colors[imgui.COLOR_MENUBAR_BACKGROUND] = theme['menubar_bg']
        style.colors[imgui.COLOR_BUTTON] = theme['button']
        style.colors[imgui.COLOR_BUTTON_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = theme['button_active']
        style.colors[imgui.COLOR_BORDER] = theme['border']
        style.colors[imgui.COLOR_TEXT] = theme['text']
        # Menu items hover (match button hover)
        style.colors[imgui.COLOR_HEADER_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_HEADER_ACTIVE] = theme['button_active']
        
        # Make popup/menu backgrounds semi-transparent for white theme
        if self.current_theme == 'white':
            # Semi-transparent white for popups/menus
            style.colors[imgui.COLOR_POPUP_BACKGROUND] = (0.94, 0.94, 0.94, 0.92)
        else:
            # Keep popup background matching window for dark themes (or slightly transparent)
            r, g, b, _ = theme['window_bg']
            style.colors[imgui.COLOR_POPUP_BACKGROUND] = (r, g, b, 0.94)
        
        # Update dark_mode flag for compatibility
        self.dark_mode = self.current_theme not in ['white']
        
        # Rounded corners (match CustomTkinter)
        style.window_rounding = 0.0  # Window itself not rounded
        style.frame_rounding = 7.0   # Match button corner_radius
        style.grab_rounding = 7.0
        
        # Padding and spacing (match CustomTkinter values)
        style.window_padding = (14, 14)
        style.frame_padding = (10, 10)
        style.item_spacing = (7, 7)  # Match grid padding
        style.window_border_size = 0.0
        style.frame_border_size = 2.0  # Match button border_width
        
        # Extra right padding for menus to prevent checkmark cutoff
        style.item_inner_spacing = (10, 4)
    
    def load_icons(self):
        """Load button icons as OpenGL textures"""
        icons = {
            "dedicated_server": "icondedicated.ico",
            "insecure": "iconinsecure.ico",
            "listen": "iconlisten.ico",
            "mapping": "hammerkz.ico",
            "source2viewer": "source2viewer.ico",
            "cs2importer": "porting.ico",
            "skyboxconverter": "skybox.ico",
            "vtf2png": "vtf2png.ico",
            "loading_screen": "loading.ico",
            "point_worldtext": "text.ico",
            "sounds": "sounds.ico",
            "title_icon": "hammerkz.ico",  # Icon for title bar
            "update_icon": "update.ico",  # Icon for update available
            "updatenot_icon": "updatenot.ico",  # Icon for no update
            "info_icon": "icon.ico"  # Icon for About menu
        }
        
        for name, filename in icons.items():
            path = resource_path(os.path.join("icons", filename))
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    # Ensure RGBA mode
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    # Use smaller size for title icon and update icon
                    if name == "title_icon":
                        img = img.resize((16, 16), Image.Resampling.LANCZOS)
                    elif name == "update_icon":
                        img = img.resize((16, 16), Image.Resampling.LANCZOS)
                    else:
                        img = img.resize((56, 56), Image.Resampling.LANCZOS)
                    width, height = img.size
                    img_data = img.tobytes()
                    
                    # Create OpenGL texture
                    texture = gl.glGenTextures(1)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
                    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height,
                                   0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data)
                    
                    self.button_icons[name] = texture
                except Exception as e:
                    print(f"✗ Error loading icon {filename} for {name}: {e}")
    
    def render_button(self, name, label, icon_key=None):
        """Render a single button with optional icon and long-press drag support"""
        if not self.button_visibility.get(name, True):
            return False
        
        # Check if this button should be disabled due to CS2 running
        # Dedicated server: disabled only when dedicated server is already running
        # Client buttons (insecure/listen/mapping): disabled when any client is running
        is_disabled = False
        if name == "dedicated_server":
            # Dedicated server is disabled only if another dedicated server is running
            is_disabled = self.cs2_dedicated_running
        elif name in ["insecure", "listen", "mapping"]:
            # Client buttons are disabled if any client is running
            is_disabled = self.cs2_client_running
        
        clicked = False
        imgui.push_id(name)
        
        # Button size depends on compact mode
        if self.compact_mode:
            button_width = BUTTON_SIZE_COMPACT_WIDTH
            button_height = BUTTON_SIZE_COMPACT_HEIGHT
            icon_size = 24
            spacing = BUTTON_SPACING_COMPACT
        else:
            button_width = BUTTON_SIZE_NON_COMPACT_WIDTH
            button_height = BUTTON_SIZE_NON_COMPACT
            icon_size = 64  # Icon size for non-compact mode
            spacing = BUTTON_SPACING
        
        # If disabled, push darker theme-based style
        if is_disabled:
            theme = self.themes.get(self.current_theme, self.themes['grey'])
            # Make button colors darker (multiply by 0.4 for disabled state)
            r, g, b, a = theme['button']
            disabled_color = (r * 0.4, g * 0.4, b * 0.4, a)
            imgui.push_style_color(imgui.COLOR_BUTTON, *disabled_color)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *disabled_color)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *disabled_color)
        
        # Button with fixed size (matching CustomTkinter)
        button_pressed = imgui.button(f"##{name}", width=button_width, height=button_height)
        is_hovered = imgui.is_item_hovered()
        
        # Show hand cursor on hover
        if is_hovered:
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)
        
        # Show tooltip on hover (only in compact mode, non-compact uses label box)
        if is_hovered and self.compact_mode:
            tooltip_text = self.get_button_tooltip(name)
            if tooltip_text:
                # Use window width minus padding for text wrapping
                tooltip_width = self.get_window_width() - 20  # 10px padding on each side
                imgui.begin_tooltip()
                imgui.push_text_wrap_pos(tooltip_width)
                
                # Just render normally - no complex color parsing
                imgui.text(tooltip_text)
                
                imgui.pop_text_wrap_pos()
                imgui.end_tooltip()
        
        # Pop disabled style if applied
        if is_disabled:
            imgui.pop_style_color(3)
        
        # Set cursor to hand when hovering over clickable buttons
        if is_hovered and not is_disabled:
            self.should_show_hand = True
        
        # Get button position for icon/text overlay
        button_min = imgui.get_item_rect_min()
        button_max = imgui.get_item_rect_max()
        draw_list = imgui.get_window_draw_list()
        
        # Store button position for drag detection
        self.button_positions[name] = (button_min.x, button_min.y, button_max.x, button_max.y)
        
        # Don't render the button being dragged in its original position
        should_render = self.dragging_button != name
        
        if should_render:
            if self.compact_mode:
                # Compact mode: icon on left, text on right
                if icon_key and icon_key in self.button_icons:
                    texture = self.button_icons[icon_key]
                    icon_x = button_min.x + 8
                    icon_y = button_min.y + (button_height - icon_size) // 2
                    
                    # Draw icon with reduced alpha if disabled
                    if is_disabled:
                        draw_list.add_image(
                            texture,
                            (icon_x, icon_y),
                            (icon_x + icon_size, icon_y + icon_size),
                            col=imgui.get_color_u32_rgba(0.5, 0.5, 0.5, 0.4)
                        )
                    else:
                        draw_list.add_image(
                            texture,
                            (icon_x, icon_y),
                            (icon_x + icon_size, icon_y + icon_size)
                        )
                    
                    # Draw text next to icon
                    text_x = icon_x + icon_size + 8
                    text_y = button_min.y + (button_height - 12) // 2
                else:
                    # No icon, just center text
                    text_x = button_min.x + 8
                    text_y = button_min.y + (button_height - 12) // 2
                
                # Draw button label (left-aligned or after icon) - grayed out if disabled
                if is_disabled:
                    text_color = imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1)
                else:
                    text_color = imgui.get_color_u32_rgba(1, 1, 1, 1) if self.dark_mode else imgui.get_color_u32_rgba(0.1, 0.1, 0.1, 1)
                
                # For compact mode, use single line (replace \n with space)
                single_line_label = label.replace('\n', ' ')
                draw_list.add_text(text_x, text_y, text_color, single_line_label)
                
                # Draw version info on the right side in compact mode
                version_lines = self.get_button_version(name)
                if version_lines:
                    # Use smaller, dimmer text for version
                    if is_disabled:
                        version_color = imgui.get_color_u32_rgba(0.3, 0.3, 0.3, 1)
                    else:
                        version_color = imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1) if self.dark_mode else imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1)
                    
                    # Use smaller font scale
                    io = imgui.get_io()
                    original_scale = io.font_global_scale
                    io.font_global_scale = 0.75
                    
                    if len(version_lines) == 2:
                        # For mapping/listen/dedicated: stack KZ and MM vertically on the right
                        line_height = 10
                        num_lines = len(version_lines)
                        
                        # Start from top of button with some padding
                        start_y = button_min.y + (button_height - (num_lines * line_height)) // 2
                        
                        for i, line in enumerate(version_lines):
                            # Extract the version part and format appropriately
                            if ': ' in line:
                                prefix, version = line.split(': ', 1)
                                # Extract version number and build separately
                                if 'build' in version:
                                    # Format: "2.0.0 (build 1367)" or "0.0.068 (build 1367)" -> extract version and build
                                    import re
                                    match = re.match(r'([\d.]+)\s*\(build\s*(\d+)\)', version)
                                    if match:
                                        ver_num = match.group(1)
                                        build_num = match.group(2)
                                        if prefix == "KZ":
                                            # Remove leading 'v' if present in ver_num
                                            ver_num = ver_num.lstrip('v')
                                            version_text = f"CS2KZ v{ver_num}"
                                        else:  # MM
                                            version_text = f"MetaMod b{build_num}"
                                    else:
                                        # No build number found in regex, use prefix
                                        if prefix == "KZ":
                                            # Remove leading 'v' if present
                                            version = version.lstrip('v')
                                            version_text = f"CS2KZ v{version}"
                                        else:
                                            version_text = f"MetaMod {version}"
                                else:
                                    # No "build" keyword, just show version with prefix
                                    if prefix == "KZ":
                                        # Remove leading 'v' if present
                                        version = version.lstrip('v')
                                        version_text = f"CS2KZ v{version}"
                                    else:
                                        version_text = f"MetaMod {version}"
                            else:
                                version_text = line
                            
                            # Calculate text width and position on right
                            text_width = imgui.calc_text_size(version_text).x
                            version_x = button_max.x - text_width - 8
                            version_y = start_y + (i * line_height)
                            
                            draw_list.add_text(version_x, version_y, version_color, version_text)
                    else:
                        # For Source2Viewer: show commit hash with color coding
                        if len(version_lines) == 2:
                            # First element is SHA, second is status
                            commit_sha = version_lines[0]
                            status = version_lines[1]
                            
                            # Color based on status
                            if status == "latest":
                                # Green for latest
                                sha_color = imgui.get_color_u32_rgba(0.3, 0.8, 0.3, 1)
                            elif status == "outdated":
                                # Orange for outdated
                                sha_color = imgui.get_color_u32_rgba(1.0, 0.6, 0.2, 1)
                            else:
                                # Default dimmed color for unknown
                                sha_color = version_color
                            
                            # Calculate text width and position on right
                            text_width = imgui.calc_text_size(commit_sha).x
                            version_x = button_max.x - text_width - 8
                            version_y = button_min.y + (button_height - 10) // 2  # Vertically centered
                            
                            # Draw the commit SHA with status color
                            draw_list.add_text(version_x, version_y, sha_color, commit_sha)
                            
                            # Detect click to open GitHub
                            mouse_pos = imgui.get_mouse_pos()
                            text_height = 10
                            if (version_x <= mouse_pos.x <= version_x + text_width and
                                version_y <= mouse_pos.y <= version_y + text_height):
                                self.should_show_hand = True
                                if imgui.is_mouse_clicked(0) and name == 'source2viewer':
                                    import webbrowser
                                    commit_url = f"https://github.com/ValveResourceFormat/ValveResourceFormat/commit/{commit_sha}"
                                    webbrowser.open(commit_url)
                        else:
                            # Single line fallback (commit hash only)
                            version_text = version_lines[0]
                            
                            # Calculate text width and position on right
                            text_width = imgui.calc_text_size(version_text).x
                            version_x = button_max.x - text_width - 8
                            version_y = button_min.y + (button_height - 10) // 2  # Vertically centered
                            
                            # Draw the commit text
                            draw_list.add_text(version_x, version_y, version_color, version_text)
                            
                            # Detect click on commit text to open GitHub commit link
                            mouse_pos = imgui.get_mouse_pos()
                            text_height = 10  # Approximate text height with 0.75 scale
                            if (version_x <= mouse_pos.x <= version_x + text_width and
                                version_y <= mouse_pos.y <= version_y + text_height):
                                # Show hand cursor
                                self.should_show_hand = True
                                # Check for click
                                if imgui.is_mouse_clicked(0) and name == 'source2viewer':
                                    # Extract commit hash from version_text
                                    import webbrowser
                                    commit_hash = version_text.strip()
                                    commit_url = f"https://github.com/ValveResourceFormat/ValveResourceFormat/commit/{commit_hash}"
                                    webbrowser.open(commit_url)
                    
                    io.font_global_scale = original_scale
            else:
                # Non-compact mode: button name at top (bold/larger), icon on left, tooltip text on right
                
                # Draw button name at the top (larger, bold-looking by drawing multiple times)
                title_x = button_min.x + 8
                title_y = button_min.y + 8
                
                if is_disabled:
                    title_color = imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1)
                else:
                    title_color = imgui.get_color_u32_rgba(1, 1, 1, 1) if self.dark_mode else imgui.get_color_u32_rgba(0.1, 0.1, 0.1, 1)
                
                # Use font scaling for larger text
                io = imgui.get_io()
                original_scale = io.font_global_scale
                io.font_global_scale = 1.3  # 30% larger
                
                button_title = label.replace('\n', ' ')
                
                # Draw title multiple times with slight offsets for bold effect
                for offset_x in [0, 0.5, 1.0]:
                    for offset_y in [0, 0.3]:
                        draw_list.add_text(title_x + offset_x, title_y + offset_y, title_color, button_title)
                
                # Restore original font scale
                io.font_global_scale = original_scale
                
                # Draw icon below title on the left
                content_y_start = button_min.y + 32  # More space for larger title
                
                if icon_key and icon_key in self.button_icons:
                    texture = self.button_icons[icon_key]
                    icon_x = button_min.x + 12
                    # Position icon to start at the same height as text (flush with text)
                    icon_y = content_y_start + 4
                    
                    # Draw icon with reduced alpha if disabled
                    if is_disabled:
                        draw_list.add_image(
                            texture,
                            (icon_x, icon_y),
                            (icon_x + icon_size, icon_y + icon_size),
                            col=imgui.get_color_u32_rgba(0.5, 0.5, 0.5, 0.4)
                        )
                    else:
                        draw_list.add_image(
                            texture,
                            (icon_x, icon_y),
                            (icon_x + icon_size, icon_y + icon_size)
                        )
                    
                    # Draw tooltip text to the right of icon
                    tooltip_text = self.get_button_tooltip(name)
                    if tooltip_text:
                        text_x = icon_x + icon_size + 8
                        text_y = content_y_start + 4
                        
                        if is_disabled:
                            text_color = imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1)
                        else:
                            text_color = imgui.get_color_u32_rgba(0.9, 0.9, 0.9, 1) if self.dark_mode else imgui.get_color_u32_rgba(0.2, 0.2, 0.2, 1)
                        
                        # Calculate max width for text wrapping (accounting for right padding)
                        max_text_width = button_max.x - text_x - 12
                        
                        # Calculate available vertical space for text (leave room for version info at bottom)
                        version_space = 28  # Space reserved for version info at bottom
                        available_height = button_max.y - text_y - version_space
                        line_height = 13
                        max_lines = int(available_height / line_height)
                        
                        # Simple word wrapping with better handling of long words
                        words = tooltip_text.split()
                        lines = []
                        current_line = ""
                        
                        for word in words:
                            test_line = current_line + (" " if current_line else "") + word
                            test_width = imgui.calc_text_size(test_line).x
                            
                            if test_width <= max_text_width:
                                current_line = test_line
                            else:
                                if current_line:
                                    lines.append(current_line)
                                    current_line = word
                                else:
                                    # Word is too long, force it and truncate with ellipsis
                                    while imgui.calc_text_size(word + "...").x > max_text_width and len(word) > 1:
                                        word = word[:-1]
                                    lines.append(word + "...")
                                    current_line = ""
                        
                        if current_line:
                            lines.append(current_line)
                        
                        # Draw each line up to max_lines
                        for i, line in enumerate(lines[:max_lines]):
                            draw_list.add_text(text_x, text_y + (i * line_height), text_color, line)
                
                # Draw version info at the bottom right of the button (stacked vertically)
                version_lines = self.get_button_version(name)
                if version_lines:
                    version_line_height = 12
                    
                    # Calculate starting Y position based on number of lines
                    num_lines = len(version_lines)
                    version_y_start = button_max.y - (num_lines * version_line_height) - 4  # 4px padding from bottom
                    
                    # Use smaller, dimmer text for version
                    if is_disabled:
                        version_color = imgui.get_color_u32_rgba(0.3, 0.3, 0.3, 1)
                    else:
                        version_color = imgui.get_color_u32_rgba(0.6, 0.6, 0.6, 1) if self.dark_mode else imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1)
                    
                    # Use smaller font scale
                    io.font_global_scale = 0.85
                    
                    # Draw each version line aligned to the right
                    for i, line in enumerate(version_lines):
                        version_y = version_y_start + (i * version_line_height)
                        # Replace "KZ:" with "CS2KZ:" for display
                        display_line = line.replace("KZ:", "CS2KZ:")
                        # Calculate text width and align to right with 8px padding
                        text_width = imgui.calc_text_size(display_line).x
                        version_x = button_max.x - text_width - 8
                        draw_list.add_text(version_x, version_y, version_color, display_line)
                        
                        # For Source2Viewer commit, detect click to open GitHub link
                        if name == 'source2viewer' and 'Commit:' in line:
                            mouse_pos = imgui.get_mouse_pos()
                            text_height = 12  # Approximate text height with 0.85 scale
                            if (version_x <= mouse_pos.x <= version_x + text_width and
                                version_y <= mouse_pos.y <= version_y + text_height):
                                # Show hand cursor
                                self.should_show_hand = True
                                # Check for click
                                if imgui.is_mouse_clicked(0):
                                    # Extract commit hash from line
                                    import webbrowser
                                    commit_hash = line.split('Commit: ')[1].strip()
                                    commit_url = f"https://github.com/ValveResourceFormat/ValveResourceFormat/commit/{commit_hash}"
                                    webbrowser.open(commit_url)
                    
                    io.font_global_scale = original_scale
        
        # Long-press drag logic (allow even if disabled)
        import time
        current_time = time.time()
        mouse_pos = imgui.get_mouse_pos()
        
        # When mouse is pressed down on this button
        if is_hovered and imgui.is_mouse_down(0):
            # Start tracking if not already tracking
            if name not in self.button_press_start_time:
                self.button_press_start_time[name] = current_time
                self.button_press_start_pos[name] = mouse_pos
            
            # Check if we should start dragging
            press_duration = current_time - self.button_press_start_time[name]
            start_pos = self.button_press_start_pos[name]
            distance_moved = ((mouse_pos.x - start_pos.x)**2 + (mouse_pos.y - start_pos.y)**2)**0.5
            
            # Start drag if held long enough OR moved far enough
            if (press_duration >= self.drag_threshold_time or distance_moved >= self.drag_threshold_distance):
                if self.dragging_button is None:
                    self.dragging_button = name
                    self.dragged_button_icon = icon_key
                    self.dragged_button_label = label
                    self.should_show_hand = True
        
        # When mouse is released on this button
        if name in self.button_press_start_time and not imgui.is_mouse_down(0):
            # Only trigger click if we're not dragging and it was a quick press (and not disabled)
            press_duration = current_time - self.button_press_start_time[name]
            start_pos = self.button_press_start_pos[name]
            distance_moved = ((mouse_pos.x - start_pos.x)**2 + (mouse_pos.y - start_pos.y)**2)**0.5
            
            if (self.dragging_button is None and 
                press_duration < self.drag_threshold_time and 
                distance_moved < self.drag_threshold_distance and
                is_hovered and
                not is_disabled):
                clicked = True
            
            # Clean up tracking for this button
            del self.button_press_start_time[name]
            del self.button_press_start_pos[name]
        
        imgui.pop_id()
        return clicked
    
    def render_custom_title_bar(self):
        """Render custom title bar with minimize and close buttons"""
        # Title bar window
        window_width = self.get_window_width()
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(window_width, CUSTOM_TITLE_BAR_HEIGHT)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        
        # Title bar background color (slightly darker than window background)
        theme = self.themes.get(self.current_theme, self.themes['grey'])
        r, g, b, a = theme['window_bg']
        # Make title bar slightly darker (multiply by 0.8)
        title_bg = (r * 0.8, g * 0.8, b * 0.8, a)
        imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, *title_bg)
        
        flags = (
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_SCROLLBAR
        )
        
        imgui.begin("##titlebar", flags=flags)
        
        # Draw icon if available
        if "title_icon" in self.button_icons:
            imgui.image(self.button_icons["title_icon"], 16, 16)
            imgui.same_line(spacing=4)
        
        # Title text with theme color
        theme = self.themes.get(self.current_theme, self.themes['grey'])
        text_color = theme['text']
        imgui.push_style_color(imgui.COLOR_TEXT, *text_color)
        imgui.text(WINDOW_TITLE)
        imgui.pop_style_color(1)
        
        # Get the position for the buttons (right side)
        button_size = 20
        button_spacing = 4
        total_button_width = (button_size * 2) + button_spacing  # Minimize + Close
        
        window_width = self.get_window_width()
        imgui.same_line(window_width - total_button_width - 6)
        
        # VS Code style buttons - flat, no borders when not hovered
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 0.0)
        
        # Minimize button (VS Code style)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)  # Transparent
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.2, 0.2, 0.2, 1.0)  # Dark gray
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)  # No border
        
        minimize_clicked = imgui.button("##minimize", width=button_size, height=button_size)
        if imgui.is_item_hovered():
            self.should_show_hand = True
        
        # Draw centered minimize symbol manually
        min_button_min = imgui.get_item_rect_min()
        min_button_max = imgui.get_item_rect_max()
        draw_list = imgui.get_window_draw_list()
        
        # Draw a centered horizontal line for minimize
        line_width = 8
        line_height = 1
        line_x = min_button_min.x + (button_size - line_width) // 2
        line_y = min_button_min.y + (button_size - line_height) // 2
        text_color = imgui.get_color_u32_rgba(0.8, 0.8, 0.8, 1.0)
        draw_list.add_rect_filled(line_x, line_y, line_x + line_width, line_y + line_height + 1, text_color)
        
        imgui.pop_style_color(4)
        
        if minimize_clicked:
            glfw.iconify_window(self.window)
        
        imgui.same_line(spacing=button_spacing)
        
        # Close button (VS Code style - red hover)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)  # Transparent
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.9, 0.2, 0.2, 1.0)  # Red
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.8, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)  # No border
        
        close_clicked = imgui.button("##close", width=button_size, height=button_size)
        if imgui.is_item_hovered():
            self.should_show_hand = True
        
        # Draw centered X symbol manually
        close_button_min = imgui.get_item_rect_min()
        close_button_max = imgui.get_item_rect_max()
        
        # Calculate center of button
        center_x = close_button_min.x + button_size // 2
        center_y = close_button_min.y + button_size // 2
        
        # Draw X with two lines
        x_size = 6
        draw_list.add_line(
            center_x - x_size // 2, center_y - x_size // 2,
            center_x + x_size // 2, center_y + x_size // 2,
            text_color, 1.5
        )
        draw_list.add_line(
            center_x + x_size // 2, center_y - x_size // 2,
            center_x - x_size // 2, center_y + x_size // 2,
            text_color, 1.5
        )
        
        imgui.pop_style_color(4)
        
        if close_clicked:
            glfw.set_window_should_close(self.window, True)
        
        # Restore style
        imgui.pop_style_var(1)
        
        # Handle window dragging from title bar
        if imgui.is_window_hovered() and imgui.is_mouse_clicked(0):
            # Check if not clicking on buttons
            mouse_pos = imgui.get_mouse_pos()
            window_width = self.get_window_width()
            if mouse_pos.x < window_width - total_button_width - 15:
                self.dragging_window = True
                window_pos = glfw.get_window_pos(self.window)
                self.drag_offset_x = mouse_pos.x
                self.drag_offset_y = mouse_pos.y
        
        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(3)
    
    def render_menu_bar(self):
        """Render menu bar"""
        if imgui.begin_menu_bar():
            # View menu
            view_menu_open = imgui.begin_menu("View")
            if imgui.is_item_hovered():
                self.should_show_hand = True
            if view_menu_open:
                for name, label in [
                    ("dedicated_server", "Dedicated Server"),
                    ("insecure", "Insecure"),
                    ("listen", "Listen"),
                    ("mapping", "Mapping"),
                    ("source2viewer", "Source2 Viewer"),
                    ("cs2importer", "CS2Importer"),
                    ("skyboxconverter", "SkyboxConverter"),
                    ("vtf2png", "VTF to PNG"),
                    ("loading_screen", "Loading Screen Stuff"),
                    ("point_worldtext", "point_worldtext"),
                    ("sounds", "Sounds Manager")
                ]:
                    clicked, new_state = imgui.menu_item(
                        label, None, self.button_visibility[name]
                    )
                    if imgui.is_item_hovered():
                        self.should_show_hand = True
                    if clicked:
                        self.button_visibility[name] = new_state
                        self.settings.set_button_visibility(name, new_state)
                        
                        # Recalculate and update window height and width
                        new_height = self.calculate_window_height()
                        new_width = self.get_window_width()
                        if new_height != self.current_window_height:
                            self.current_window_height = new_height
                            glfw.set_window_size(self.window, new_width, new_height)
                imgui.end_menu()
            
            # Links menu
            links_menu_open = imgui.begin_menu("Links")
            if imgui.is_item_hovered():
                self.should_show_hand = True
            if links_menu_open:
                # Mapping API Wiki
                if imgui.menu_item("Mapping API Wiki")[0]:
                    import webbrowser
                    webbrowser.open("https://github.com/KZGlobalTeam/cs2kz-metamod/wiki/Mapping-API")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                # CS2KZ Metamod
                if imgui.menu_item("CS2KZ Metamod")[0]:
                    import webbrowser
                    webbrowser.open("https://github.com/KZGlobalTeam/cs2kz-metamod")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                # cs2kz.org
                if imgui.menu_item("cs2kz.org")[0]:
                    import webbrowser
                    webbrowser.open("https://cs2kz.org")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                # Source2Viewer
                if imgui.menu_item("Source2Viewer")[0]:
                    import webbrowser
                    webbrowser.open("https://s2v.app/")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                imgui.separator()
                
                # Assets header (non-clickable)
                imgui.text("Assets")
                
                # AmbientCG
                if imgui.menu_item("  AmbientCG")[0]:
                    import webbrowser
                    webbrowser.open("https://ambientcg.com/")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                # Sketchfab
                if imgui.menu_item("  Sketchfab")[0]:
                    import webbrowser
                    webbrowser.open("https://sketchfab.com/search?features=downloadable&type=models")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                # Meshes
                if imgui.menu_item("  Meshes")[0]:
                    import webbrowser
                    webbrowser.open("https://www.thebasemesh.com/model-library")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                # JP-2499/AgX
                if imgui.menu_item("  JP-2499/AgX")[0]:
                    import webbrowser
                    webbrowser.open("https://codeberg.org/GameChaos/s2-open-domain-lut-generator/releases/tag/jp2499-v1")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                # GameBanana
                if imgui.menu_item("  GameBanana")[0]:
                    import webbrowser
                    webbrowser.open("https://gamebanana.com/games/4660")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                
                imgui.end_menu()
            
            # Settings menu
            # In compact mode, make menu wider and position it more to the left
            if self.compact_mode:
                menu_width = 220  # Wider menu for compact mode
            else:
                menu_width = 220  # Fixed width for Settings menu in non-compact mode
            imgui.push_style_var(imgui.STYLE_ITEM_INNER_SPACING, (15, 4))  # Spacing between text and checkbox in menu items
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (2, 12))  # Reduce window padding to fit content
            imgui.set_next_window_size(menu_width, 0)
            settings_menu_open = imgui.begin_menu("Settings")
            if imgui.is_item_hovered():
                self.should_show_hand = True
            if settings_menu_open:
                # Constrain menu item width to ensure checkboxes fit
                item_width = min(180, menu_width - 20)
                imgui.set_next_item_width(item_width)
                
                # Theme submenu
                theme_menu_open = imgui.begin_menu("Theme")
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                if theme_menu_open:
                    themes = ['Grey', 'Black', 'White', 'Pink', 'Orange', 'Blue', 'Red', 'Green', 'Yellow', 'Dracula']
                    for theme_name in themes:
                        theme_key = theme_name.lower()
                        is_selected = self.current_theme == theme_key
                        clicked, _ = imgui.menu_item(theme_name, None, is_selected)
                        if imgui.is_item_hovered():
                            self.should_show_hand = True
                        if clicked and not is_selected:
                            self.current_theme = theme_key
                            self.settings.set('appearance_mode', theme_key)
                            self.setup_style()
                    imgui.end_menu()
                
                # Compact Mode
                imgui.set_next_item_width(item_width)
                clicked_compact, new_compact_mode = imgui.menu_item(
                    "Compact Mode", None, self.compact_mode
                )
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                if clicked_compact:
                    self.compact_mode = new_compact_mode
                    self.settings.set('compact_mode', self.compact_mode)
                    # Mark that window needs resize (will happen after menu closes)
                    self.needs_window_resize = True
                
                # Always on Top
                imgui.set_next_item_width(item_width)
                clicked_top, new_always_on_top = imgui.menu_item(
                    "Always on Top", None, self.always_on_top
                )
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                if clicked_top:
                    self.always_on_top = new_always_on_top
                    self.settings.set('always_on_top', self.always_on_top)
                    glfw.set_window_attrib(self.window, glfw.FLOATING, glfw.TRUE if self.always_on_top else glfw.FALSE)
                
                # Window Opacity Slider (compact single-line with text on left)
                imgui.text("Opacity")
                imgui.same_line()
                
                # Make the slider thinner with minimal padding
                imgui.push_style_var(imgui.STYLE_FRAME_PADDING, (4, 2))
                imgui.push_style_var(imgui.STYLE_GRAB_MIN_SIZE, 8)
                imgui.set_next_item_width(120)
                changed, new_opacity = imgui.slider_float("##opacity", self.window_opacity, 0.1, 1.0, "%.2f")
                if imgui.is_item_hovered() or imgui.is_item_active():
                    self.should_show_hand = True
                imgui.pop_style_var(2)
                
                if changed:
                    self.window_opacity = new_opacity
                    self.settings.set('window_opacity', new_opacity)
                    glfw.set_window_opacity(self.window, new_opacity)
                
                # Separator before button-related options
                imgui.separator()
                
                # Button-related options
                imgui.set_next_item_width(item_width)
                clicked, new_state = imgui.menu_item(
                    "Auto Update Source2Viewer", None, self.auto_update_source2viewer
                )
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                if clicked:
                    self.auto_update_source2viewer = new_state
                    self.settings.set('auto_update_source2viewer', new_state)
                
                # Auto Update Metamod
                imgui.set_next_item_width(item_width)
                clicked, new_state = imgui.menu_item(
                    "Auto Update Metamod", None, self.auto_update_metamod
                )
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                if clicked:
                    self.auto_update_metamod = new_state
                    self.settings.set('auto_update_metamod', new_state)
                
                # Auto Update CS2KZ
                imgui.set_next_item_width(item_width)
                clicked, new_state = imgui.menu_item(
                    "Auto Update CS2KZ", None, self.auto_update_cs2kz
                )
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                if clicked:
                    self.auto_update_cs2kz = new_state
                    self.settings.set('auto_update_cs2kz', new_state)
                
                # Separator before clear data options
                imgui.separator()
                
                # Data (open folder) - clickable header that opens data folder
                if imgui.menu_item("Temp folder (open folder)")[0]:
                    self.open_data_folder()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Open the folder containing\napp data and cache files")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Clear Settings
                if imgui.menu_item("  Clear Settings")[0]:
                    self.clear_settings()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Clear saved app settings\n(theme, window position, button\nvisibility, etc)")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Clear Version Cache
                if imgui.menu_item("  Clear Version Cache")[0]:
                    self.clear_version_cache()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Clear saved Metamod/CS2KZ\nversion information\n(forces update check)")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Clear Temp Folder
                if imgui.menu_item("  Clear Temp Folder")[0]:
                    self.clear_temp_folder()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Clear files and folders (keeps\nSource2Viewer and settings)")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Remove Source2Viewer
                if imgui.menu_item("  Remove Source2Viewer")[0]:
                    self.remove_source2viewer()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Remove Source2Viewer executable\nfrom the temp folder")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                imgui.separator()
                
                # Verify Game Files
                if imgui.menu_item("Manually Verify Files")[0]:
                    self.verify_game_files()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Restore modified game files to\noriginal state from GitHub\nTracker")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                imgui.end_menu()
            imgui.pop_style_var(2)  # Pop both style variables
            
            # Push icons to the right side of the menu bar
            # Calculate available space and add spacing
            menu_bar_width = imgui.get_window_width()
            cursor_x = imgui.get_cursor_pos_x()
            info_icon_width = 16  # Info icon width
            update_icon_width = 16 + 8  # Update icon width + spacing between icons
            right_padding = 10  # Extra padding to prevent cutoff
            spacing = menu_bar_width - cursor_x - info_icon_width - update_icon_width - right_padding
            
            if spacing > 0:
                imgui.set_cursor_pos_x(cursor_x + spacing)
            
            # Update icon - switch between updatenot.ico and update.ico based on availability
            if "update_icon" in self.button_icons and "updatenot_icon" in self.button_icons:
                # Choose icon based on update availability
                if self.update_available:
                    update_texture = self.button_icons["update_icon"]
                else:
                    update_texture = self.button_icons["updatenot_icon"]
                
                # Save current Y position
                current_y = imgui.get_cursor_pos_y()
                
                # Align vertically with menu text (center the 16px icon with text line height)
                y_offset = (imgui.get_frame_height() - 16) / 2
                imgui.set_cursor_pos_y(current_y + y_offset)
                
                # Render as plain image (clickable)
                imgui.image(update_texture, 16, 16)
                
                # Check if clicked
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    if imgui.is_mouse_clicked(0) and self.update_available:
                        self.perform_update()
                    
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    if self.update_available:
                        imgui.text("Update available!")
                        imgui.text("")
                        if self.update_checker.latest_version_tag:
                            imgui.text("New version:")
                            imgui.text(self.update_checker.latest_version_tag)
                        if self.update_checker.latest_version_date:
                            date_str = self.update_checker.latest_version_date.strftime("%Y-%m-%d")
                            time_str = self.update_checker.latest_version_date.strftime("%H:%M")
                            imgui.text(date_str)
                            imgui.text(time_str)
                        imgui.text("")
                        if self.update_checker.current_version_date:
                            current_date_str = self.update_checker.current_version_date.strftime("%Y-%m-%d")
                            current_time_str = self.update_checker.current_version_date.strftime("%H:%M")
                            imgui.text("Current version:")
                            imgui.text(current_date_str)
                            imgui.text(current_time_str)
                        imgui.text("")
                        imgui.text("Click to open")
                        imgui.text("GitHub Releases")
                    else:
                        imgui.text("Check for updates")
                        imgui.text("")
                        imgui.text("Click to open")
                        imgui.text("GitHub Releases")
                        if self.update_checker and self.update_checker.current_version_date:
                            imgui.text("")
                            current_date_str = self.update_checker.current_version_date.strftime("%Y-%m-%d")
                            current_time_str = self.update_checker.current_version_date.strftime("%H:%M")
                            imgui.text("Current version:")
                            imgui.text(current_date_str)
                            imgui.text(current_time_str)
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                imgui.same_line(spacing=8)  # Small spacing before About menu
                imgui.set_cursor_pos_y(current_y)  # Restore Y position for About menu
            
            # About menu using info icon instead of text
            if "info_icon" in self.button_icons:
                info_texture = self.button_icons["info_icon"]
                
                # Save current Y position
                current_y = imgui.get_cursor_pos_y()
                
                # Align vertically with menu text
                y_offset = (imgui.get_frame_height() - 16) / 2
                imgui.set_cursor_pos_y(current_y + y_offset)
                
                # Render info icon as plain image
                imgui.image(info_texture, 16, 16)
                
                # Check if clicked to open menu
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    if imgui.is_mouse_clicked(0):
                        imgui.open_popup("about_popup")
                
                imgui.set_cursor_pos_y(current_y)  # Restore Y position
                
                # About popup menu
                if imgui.begin_popup("about_popup"):
                    # Credits with clickable names
                    imgui.text("Made by ")
                    imgui.same_line(spacing=0)
                    
                    # jakke link - use selectable with exact width for inline layout
                    jakke_width = imgui.calc_text_size("jakke").x
                    jakke_clicked = imgui.selectable("jakke", False, flags=imgui.SELECTABLE_DONT_CLOSE_POPUPS, width=jakke_width)[0]
                    if imgui.is_item_hovered():
                        self.should_show_hand = True
                    if jakke_clicked:
                        import webbrowser
                        import threading
                        threading.Thread(target=lambda: webbrowser.open("http://steamcommunity.com/profiles/76561197981712950"), daemon=True).start()
                    
                    # Open Github link
                    github_clicked = imgui.menu_item("Open Github")[0]
                    if imgui.is_item_hovered():
                        self.should_show_hand = True
                    if github_clicked:
                        import webbrowser
                        import threading
                        threading.Thread(target=lambda: webbrowser.open("https://github.com/jakkekz/CS2KZ-Mapping-Tools"), daemon=True).start()
                    
                    imgui.end_popup()
            
            imgui.end_menu_bar()
    
    def render_ui(self):
        """Render the main UI - called every frame"""
        # Handle deferred window resize (only when not in a menu to avoid layout issues)
        if self.needs_window_resize and not imgui.is_popup_open("", imgui.POPUP_ANY_POPUP_ID):
            expected_height = self.calculate_window_height()
            expected_width = self.get_window_width()
            self.current_window_height = expected_height
            glfw.set_window_size(self.window, expected_width, expected_height)
            self.needs_window_resize = False
        
        # Reset hand cursor flag at start of frame
        self.should_show_hand = False
        
        # Render custom title bar first
        self.render_custom_title_bar()
        
        # Set window flags - no scrollbars since we size the window to fit content
        flags = (
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_COLLAPSE |
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE |
            imgui.WINDOW_NO_TITLE_BAR |  # Remove the title bar
            imgui.WINDOW_MENU_BAR
        )
        
        # Main window - positioned below title bar
        window_width = self.get_window_width()
        imgui.set_next_window_position(0, CUSTOM_TITLE_BAR_HEIGHT)
        imgui.set_next_window_size(window_width, self.current_window_height - CUSTOM_TITLE_BAR_HEIGHT)
        
        # Make window background transparent to show background image
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (14, 14))
        
        imgui.begin("##main", flags=flags)  # Use ## to hide label
        
        # Menu bar
        self.render_menu_bar()
        
        # Button configurations with display names
        button_configs = {
            "dedicated_server": ("Dedicated\nServer", "dedicated_server"),
            "insecure": ("Insecure", "insecure"),
            "listen": ("Listen", "listen"),
            "mapping": ("Mapping", "mapping"),
            "source2viewer": ("Source2Viewer", "source2viewer"),
            "cs2importer": ("CS2 Map\nImporter", "cs2importer"),
            "skyboxconverter": ("Skybox\nConverter", "skyboxconverter"),
            "vtf2png": ("VTF to PNG", "vtf2png"),
            "loading_screen": ("Loading\nScreen", "loading_screen"),
            "point_worldtext": ("point_worldtext", "point_worldtext"),
            "sounds": ("Sound\nManager", "sounds")
        }
        
        # Render buttons in order, 3 columns for non-compact or 1 column for compact mode
        col = 0
        max_cols = 1 if self.compact_mode else 3
        spacing_val = BUTTON_SPACING_COMPACT if self.compact_mode else BUTTON_SPACING
        
        for button_name in self.button_order:
            if button_name in button_configs and self.button_visibility.get(button_name, True):
                label, icon = button_configs[button_name]
                
                if col > 0:
                    imgui.same_line(spacing=spacing_val)
                
                if self.render_button(button_name, label, icon):
                    self.handle_button_click(button_name)
                
                col += 1
                if col >= max_cols:
                    col = 0
        
        # Check which button the mouse is over during drag
        if self.dragging_button is not None:
            mouse_pos = imgui.get_mouse_pos()
            self.hover_target = None
            
            # Check mouse position against all button bounds
            for btn_name, (min_x, min_y, max_x, max_y) in self.button_positions.items():
                if btn_name != self.dragging_button:
                    if min_x <= mouse_pos.x <= max_x and min_y <= mouse_pos.y <= max_y:
                        self.hover_target = btn_name
                        break
            
            # Draw the dragged button following the mouse cursor
            draw_list = imgui.get_window_draw_list()
            
            # Button size depends on compact mode
            if self.compact_mode:
                button_width = BUTTON_SIZE_COMPACT_WIDTH
                button_height = BUTTON_SIZE_COMPACT_HEIGHT
                icon_size = 24
            else:
                button_width = BUTTON_SIZE_NON_COMPACT_WIDTH
                button_height = BUTTON_SIZE_NON_COMPACT
                icon_size = 64
            
            drag_x = mouse_pos.x - button_width // 2
            drag_y = mouse_pos.y - button_height // 2
            
            # Draw semi-transparent button background
            bg_color = imgui.get_color_u32_rgba(0.29, 0.29, 0.29, 0.8) if self.dark_mode else imgui.get_color_u32_rgba(0.75, 0.75, 0.75, 0.8)
            draw_list.add_rect_filled(drag_x, drag_y, drag_x + button_width, drag_y + button_height, bg_color, 7.0)
            
            # Draw icon if available
            text_color = imgui.get_color_u32_rgba(1, 1, 1, 1) if self.dark_mode else imgui.get_color_u32_rgba(0.1, 0.1, 0.1, 1)
            
            if self.compact_mode:
                # Compact mode: icon on left, text on right
                if self.dragged_button_icon and self.dragged_button_icon in self.button_icons:
                    texture = self.button_icons[self.dragged_button_icon]
                    icon_x = drag_x + 8
                    icon_y = drag_y + (button_height - icon_size) // 2
                    draw_list.add_image(texture, (icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size))
                    text_x = icon_x + icon_size + 8
                    text_y = drag_y + (button_height - 12) // 2
                else:
                    text_x = drag_x + 8
                    text_y = drag_y + (button_height - 12) // 2
                
                # Draw label (single line)
                single_line_label = self.dragged_button_label.replace('\n', ' ')
                draw_list.add_text(text_x, text_y, text_color, single_line_label)
            else:
                # Non-compact mode: icon on left, text on right (same as stationary buttons)
                if self.dragged_button_icon and self.dragged_button_icon in self.button_icons:
                    texture = self.button_icons[self.dragged_button_icon]
                    icon_x = drag_x + 12
                    icon_y = drag_y + (button_height - icon_size) // 2
                    draw_list.add_image(texture, (icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size))
                    text_x = icon_x + icon_size + 12
                    text_y = drag_y + (button_height - 12) // 2
                else:
                    text_x = drag_x + 12
                    text_y = drag_y + (button_height - 12) // 2
                
                # Draw label (single line)
                single_line_label = self.dragged_button_label.replace('\n', ' ')
                draw_list.add_text(text_x, text_y, text_color, single_line_label)
        
        # Handle global drag-drop release (swap buttons when mouse is released)
        if imgui.is_mouse_released(0) and self.dragging_button is not None:
            if self.hover_target is not None:
                self.swap_buttons(self.dragging_button, self.hover_target)
            self.dragging_button = None
            self.hover_target = None
            self.dragged_button_icon = None
            self.dragged_button_label = None
        
        imgui.end()
        imgui.pop_style_var(2)
        
        # Apply hand cursor if any menu item was hovered
        if self.should_show_hand:
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)
    
    def handle_button_click(self, button_name):
        """Handle button clicks"""
        def run_script_module(module_path, args=None):
            """Run a script module in a separate thread (for non-GUI scripts)"""
            def run():
                try:
                    # Set sys.argv for the script
                    old_argv = sys.argv.copy()
                    script_name = os.path.basename(module_path)
                    sys.argv = [script_name] + (args or [])
                    
                    # Execute the script
                    with open(module_path, 'r', encoding='utf-8') as f:
                        code = f.read()
                        exec(code, {'__name__': '__main__', '__file__': module_path})
                    
                    # Restore sys.argv
                    sys.argv = old_argv
                except Exception as e:
                    print(f"Error running {module_path}: {e}")
                    import traceback
                    traceback.print_exc()
            
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
        
        def run_gui_executable(exe_name):
            """Run a bundled GUI executable directly from gui_tools folder (onedir format)"""
            try:
                # If running from source (not frozen), run Python scripts directly
                if not getattr(sys, 'frozen', False):
                    # Map exe names to script paths
                    script_map = {
                        "CS2Importer.exe": "scripts/porting/cs2importer.py",
                        "SkyboxConverter.exe": "scripts/skybox_gui.py",
                        "VTF2PNG.exe": "scripts/vtf2png_gui.py",
                        "LoadingScreenCreator.exe": "scripts/loading_screen_gui.py",
                        "PointWorldText.exe": "scripts/pointworldtext.py",
                        "Sounds.exe": "scripts/sounds.py"
                    }
                    script_path = script_map.get(exe_name)
                    if script_path:
                        subprocess.Popen([sys.executable, script_path])
                        return
                
                # With onedir main exe, GUI tools are directly in gui_tools folder
                # No extraction needed - just run them directly!
                folder_name = exe_name.replace('.exe', '')
                gui_tool_folder = resource_path(os.path.join('gui_tools', folder_name))
                gui_tool_exe = os.path.join(gui_tool_folder, exe_name)
                
                if not os.path.exists(gui_tool_exe):
                    print(f"Error: {exe_name} not found at {gui_tool_exe}")
                    return
                
                # Run the GUI tool directly from the main folder
                try:
                    subprocess.Popen([gui_tool_exe])
                    print(f"Launched {gui_tool_exe}")
                except Exception as launch_error:
                    print(f"Error launching {exe_name}: {launch_error}")
                    import traceback
                    traceback.print_exc()
                    
            except Exception as e:
                print(f"Error launching GUI executable {exe_name}: {e}")
                import traceback
                traceback.print_exc()
        
        if button_name == "dedicated_server":
            args = []
            if not self.auto_update_metamod:
                args.append('--no-update-metamod')
            if not self.auto_update_cs2kz:
                args.append('--no-update-cs2kz')
            script_path = resource_path(os.path.join("scripts", "run-dedicated.py"))
            run_script_module(script_path, args)
        
        elif button_name == "insecure":
            script_path = resource_path(os.path.join("scripts", "run-insecure.py"))
            run_script_module(script_path)
        
        elif button_name == "listen":
            args = []
            if not self.auto_update_metamod:
                args.append('--no-update-metamod')
            if not self.auto_update_cs2kz:
                args.append('--no-update-cs2kz')
            script_path = resource_path(os.path.join("scripts", "listen.py"))
            run_script_module(script_path, args)
        
        elif button_name == "mapping":
            args = []
            if not self.auto_update_metamod:
                args.append('--no-update-metamod')
            if not self.auto_update_cs2kz:
                args.append('--no-update-cs2kz')
            script_path = resource_path(os.path.join("scripts", "mapping.py"))
            run_script_module(script_path, args)
        
        elif button_name == "source2viewer":
            if self.auto_update_source2viewer:
                script_path = resource_path(os.path.join("scripts", "S2V-AUL.py"))
                run_script_module(script_path)
            else:
                # Launch Source2Viewer.exe directly from temp folder
                temp_dir = self.settings.temp_dir
                s2v_path = os.path.join(temp_dir, '.CS2KZ-mapping-tools', 'Source2Viewer.exe')
                
                if os.path.exists(s2v_path):
                    try:
                        subprocess.Popen([s2v_path])
                    except Exception as e:
                        print(f"Error launching Source2Viewer: {e}")
                else:
                    print(f"Warning: Source2Viewer.exe not found at {s2v_path}")
                    print("Enable auto-update in Settings to download it automatically.")
        
        elif button_name == "cs2importer":
            # GUI app - extract and run bundled executable
            run_gui_executable("CS2Importer.exe")
        
        elif button_name == "skyboxconverter":
            # GUI app - extract and run bundled executable
            run_gui_executable("SkyboxConverter.exe")
        
        elif button_name == "vtf2png":
            # GUI app - extract and run bundled executable
            run_gui_executable("VTF2PNG.exe")
        
        elif button_name == "loading_screen":
            # GUI app - extract and run bundled executable
            run_gui_executable("LoadingScreenCreator.exe")
        
        elif button_name == "point_worldtext":
            # GUI app - extract and run bundled executable
            run_gui_executable("PointWorldText.exe")
        
        elif button_name == "sounds":
            # GUI app - extract and run bundled executable
            run_gui_executable("Sounds.exe")
    
    def run(self):
        """Main application loop"""
        self.init_window()
        
        # Track time for CS2 detection
        import time
        last_cs2_check = 0
        cs2_check_interval = 2.0  # Check every 2 seconds (reduced overhead)
        
        # Track time for update checking
        last_update_check = 0
        update_check_interval = 10.0 * 60  # Check every 10 minutes (converted to seconds)
        
        # Do initial update check on startup
        threading.Thread(target=self.check_for_updates, daemon=True).start()
        
        # Track if window has been shown (to prevent black flash)
        window_shown = False
        
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.impl.process_inputs()
            
            # Periodically check if CS2 is running
            current_time = time.time()
            if current_time - last_cs2_check >= cs2_check_interval:
                self.cs2_client_running, self.cs2_dedicated_running = self.is_cs2_running()
                last_cs2_check = current_time
            
            # Periodically check for updates (every 5 minutes)
            if current_time - last_update_check >= update_check_interval:
                threading.Thread(target=self.check_for_updates, daemon=True).start()
                last_update_check = current_time
            
            # Reset cursor flags at the start of each frame
            self.should_show_hand = False
            
            # Handle window dragging
            if self.dragging_window:
                if imgui.is_mouse_down(0):
                    # Update window position while dragging
                    mouse_x, mouse_y = glfw.get_cursor_pos(self.window)
                    window_pos = glfw.get_window_pos(self.window)
                    new_x = int(window_pos[0] + mouse_x - self.drag_offset_x)
                    new_y = int(window_pos[1] + mouse_y - self.drag_offset_y)
                    glfw.set_window_pos(self.window, new_x, new_y)
                else:
                    # Stop dragging when mouse released
                    self.dragging_window = False
            
            # Handle font reload if needed (must be done BEFORE new_frame)
            if hasattr(self, '_needs_font_reload') and self._needs_font_reload:
                io = imgui.get_io()
                io.fonts.clear()
                
                # Always use Consolas font
                consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
                if os.path.exists(consolas_path):
                    io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
                else:
                    # Fallback to Roboto
                    font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
                    if os.path.exists(font_path):
                        io.fonts.add_font_from_file_ttf(font_path, 13.0)
                
                # Rebuild font atlas
                self.impl.refresh_font_texture()
                
                self._last_theme_for_font = self.current_theme
                self._needs_font_reload = False
            
            # Start ImGui frame first
            imgui.new_frame()
            
            # Render UI
            self.render_ui()
            
            # Set cursor based on whether any imgui item wants hover cursor
            if imgui.is_any_item_hovered() or self.should_show_hand:
                glfw.set_cursor(self.window, self.hand_cursor)
            else:
                glfw.set_cursor(self.window, self.arrow_cursor)
            
            # Rendering
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            
            imgui.render()
            self.impl.render(imgui.get_draw_data())
            
            glfw.swap_buffers(self.window)
            
            # Show window after first frame is rendered to prevent black flash
            if not window_shown:
                glfw.show_window(self.window)
                window_shown = True
        
        # Save window position before closing
        pos = glfw.get_window_pos(self.window)
        self.settings.set_window_position(pos[0], pos[1])
        
        # Save all settings
        for name, visible in self.button_visibility.items():
            self.settings.set_button_visibility(name, visible)
        
        self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        # Clean up Source2Viewer download flag if it exists
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        download_flag = os.path.join(app_dir, '.s2v_downloading')
        try:
            if os.path.exists(download_flag):
                os.remove(download_flag)
                print("Cleaned up download flag")
        except Exception as e:
            print(f"Could not remove download flag: {e}")
        
        # Destroy custom cursors
        if self.arrow_cursor:
            glfw.destroy_cursor(self.arrow_cursor)
        if self.hand_cursor:
            glfw.destroy_cursor(self.hand_cursor)
        
        self.impl.shutdown()
        glfw.terminate()


if __name__ == "__main__":
    try:
        app = ImGuiApp()
        app.run()
    except ImportError as e:
        print(f"\nMissing dependency: {e}")
        print("\nInstall required packages with:")
        print("  pip install imgui[glfw] PyOpenGL pillow")
        print("\nOr install all at once:")
        print("  pip install imgui[glfw] PyOpenGL pillow")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
