"""
CS2 Sounds Manager - PyImGui Interface
Simplifies adding custom sounds to CS2 maps
"""

import imgui
import glfw
from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
import sys
import subprocess
import os
import re
import shutil
import tempfile
import winreg
import vdf
from tkinter import filedialog
import tkinter as tk
from PIL import Image
import threading
import vpk
import pygame

# Try to import VSND decompiler
try:
    from vsnd_decompiler import VSNDDecompiler
    VSND_DECOMPILER = VSNDDecompiler()
except Exception as e:
    print(f"Warning: VSND decompiler not available: {e}")
    VSND_DECOMPILER = None

# Constants
CUSTOM_TITLE_BAR_HEIGHT = 30


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Import theme manager after resource_path is defined
sys.path.insert(0, resource_path('utils'))
from theme_manager import ThemeManager


class SoundsManagerApp:
    def __init__(self):
        self.window = None
        self.impl = None
        
        # Theme manager
        self.theme_manager = ThemeManager()
        
        # Application state
        self.cs2_basefolder = None
        self.addon_name = ""
        
        # Sound source toggle
        self.use_internal_sound = False  # False = custom file, True = internal CS2 sound
        
        # Custom sound file
        self.sound_file_path = ""
        self.sound_file_display = "None selected"
        self.sound_name = ""  # Name for the soundevent (without extension)
        
        # Internal sound browser
        self.internal_sounds = []  # List of internal sound paths from VPK
        self.internal_sounds_tree = {}  # Hierarchical structure for tree display
        self.internal_sounds_loaded = False
        self.loading_internal_sounds = False
        self.selected_internal_sound = ""
        self.internal_sound_filter = ""
        self.filtered_internal_sounds = []
        
        # Audio preview (pygame mixer)
        self.preview_sound = None
        self.preview_playing = False
        self.preview_volume = 0.5  # Default preview volume at 50%
        pygame.mixer.init()
        pygame.mixer.music.set_volume(self.preview_volume)
        
        # VSND decompiler for internal sound preview
        self.vsnd_decompiler = None
        try:
            from vsnd_decompiler import VSNDDecompiler
            self.vsnd_decompiler = VSNDDecompiler()
        except Exception as e:
            print(f"Note: VSND decompiler not available: {e}")
            print("  Internal sound preview requires .NET Desktop Runtime 9.0")
        
        # Addon autocomplete
        self.available_addons = []
        self.filtered_addons = []
        self.show_addon_dropdown = False
        self.selected_addon_index = -1
        self.addon_just_selected = False  # Flag to force input update
        
        # Sound parameters with default values
        self.sound_type = "csgo_mega"  # Default sound type
        self.volume = 1.0
        self.pitch = 1.0
        self.distance_near = 0.0
        self.distance_near_volume = 1.0
        self.distance_mid = 1000.0
        self.distance_mid_volume = 0.5
        self.distance_far = 3000.0
        self.distance_far_volume = 0.0
        self.occlusion_intensity = 100.0
        
        # Toggle states for UI controls
        self.show_pitch = False  # Default: hidden
        self.show_occlusion = False  # Default: hidden
        
        # UI state
        self.sound_status_color = (1.0, 0.0, 0.0, 1.0)    # Red initially
        
        # Custom title bar drag state
        self.dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Console output
        self.console_output = []
        self.last_console_line_count = 0
        
        # Icon texture
        self.title_icon = None
        
        # Cursors (will be created after window initialization)
        self.arrow_cursor = None
        self.hand_cursor = None
        
        # Theme tracking
        self.current_theme_name = self.theme_manager.get_theme_name()
        
        # Detect CS2 path
        self.detect_cs2_path()
        
        # Clean up old preview cache on startup
        cache_dir = os.path.join(tempfile.gettempdir(), '.CS2KZ-mapping-tools', 'sound_preview')
        if os.path.exists(cache_dir):
            self.cleanup_preview_cache(cache_dir, max_files=5)
        
        # Window dimensions - will be adjusted dynamically based on content
        self.window_width = 900  # Adjusted for narrower left panel
        self.left_panel_width = 300  # Narrower since we show only filenames now
        self.right_panel_width = 600  # window_width - left_panel_width
        self.content_height = 0  # Will be calculated during first render
        self.base_window_height = 500  # Initial height, will scale dynamically based on content
    
    def detect_cs2_path(self):
        """Detect CS2 installation path from Steam"""
        try:
            # Read Steam path from registry
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            except FileNotFoundError:
                self.log("✗ Steam installation not found in registry")
                return False
            
            # Read libraryfolders.vdf to find CS2
            libraryfolders_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
            if not os.path.exists(libraryfolders_path):
                self.log("✗ Steam library folders not found")
                return False
            
            with open(libraryfolders_path, 'r', encoding='utf-8') as file:
                library_data = vdf.load(file)
            
            # Find CS2 (appid 730)
            cs2_library_path = None
            if 'libraryfolders' in library_data:
                for _, folder in library_data['libraryfolders'].items():
                    if 'apps' in folder and '730' in folder['apps']:
                        cs2_library_path = folder['path']
                        break
            
            if not cs2_library_path:
                self.log("✗ CS2 installation not found in Steam libraries")
                return False
            
            self.cs2_basefolder = os.path.join(cs2_library_path, 'steamapps', 'common', 'Counter-Strike Global Offensive')
            
            if os.path.exists(self.cs2_basefolder):
                self.log(f"✓ CS2 detected at: {self.cs2_basefolder}")
                return True
            else:
                self.log(f"✗ CS2 folder not found at {self.cs2_basefolder}")
                return False
                
        except Exception as e:
            self.log(f"✗ Error detecting CS2 path: {e}")
            return False
    
    def scan_available_addons(self):
        """Scan for available addons in csgo_addons folder"""
        if not self.cs2_basefolder:
            return []
        
        addons_path = os.path.join(self.cs2_basefolder, 'content', 'csgo_addons')
        if not os.path.exists(addons_path):
            return []
        
        try:
            # Get all directories in csgo_addons
            addons = [d for d in os.listdir(addons_path) 
                     if os.path.isdir(os.path.join(addons_path, d))]
            return sorted(addons)
        except Exception as e:
            self.log(f"✗ Error scanning addons: {e}")
            return []
    
    def load_internal_sounds(self):
        """Load internal CS2 sounds from VPK in background thread"""
        if not self.cs2_basefolder:
            self.log("✗ CS2 path not detected")
            return
        
        self.loading_internal_sounds = True
        self.log("Loading internal CS2 sounds from VPK...")
        
        def load_thread():
            try:
                pak_path = os.path.join(self.cs2_basefolder, 'game', 'csgo', 'pak01_dir.vpk')
                if not os.path.exists(pak_path):
                    self.log(f"✗ VPK not found at: {pak_path}")
                    self.loading_internal_sounds = False
                    return
                
                # Open VPK
                pak = vpk.open(pak_path)
                
                # Extract all sound paths
                sounds = []
                vsnd_count = 0
                for filepath in pak:
                    # Look for vsnd_c files (compiled sounds)
                    if filepath.endswith('.vsnd_c'):
                        vsnd_count += 1
                        # Check if it's in sounds folder (use backslash for Windows paths)
                        if 'sounds' in filepath.lower():
                            # Remove .vsnd_c extension for display
                            sound_path = filepath.replace('.vsnd_c', '')
                            sounds.append(sound_path)
                
                self.internal_sounds = sorted(sounds)
                self.filtered_internal_sounds = self.internal_sounds
                self.internal_sounds_loaded = True
                self.loading_internal_sounds = False
                self.log(f"✓ Loaded {len(sounds)} internal sounds")
                
            except Exception as e:
                self.log(f"✗ Error loading internal sounds: {e}")
                self.loading_internal_sounds = False
        
        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()
    
    def filter_internal_sounds(self, search_text):
        """Filter internal sounds based on search text"""
        if not search_text:
            self.filtered_internal_sounds = self.internal_sounds
        else:
            search_lower = search_text.lower()
            self.filtered_internal_sounds = [
                sound for sound in self.internal_sounds
                if search_lower in sound.lower()
            ]
    
    def cleanup_preview_cache(self, cache_dir, max_files=5, make_room_for_new=False):
        """Keep only the most recent N preview files in cache"""
        try:
            if not os.path.exists(cache_dir):
                return
                
            # Get all files in cache directory (audio files with or without extensions)
            cache_files = []
            try:
                for f in os.listdir(cache_dir):
                    file_path = os.path.join(cache_dir, f)
                    # Only include files (not directories)
                    if os.path.isfile(file_path):
                        cache_files.append(file_path)
            except Exception as e:
                print(f"Warning: Could not list cache directory: {e}")
                return
            
            # Debug: show what we found
            if cache_files:
                print(f"🔍 Found {len(cache_files)} files in cache")
            
            # Determine how many files to keep
            if make_room_for_new:
                # Keep max_files - 1 to make room for incoming file
                target_count = max_files - 1
            else:
                # Keep exactly max_files
                target_count = max_files
            
            # If we have more than target, delete oldest
            if len(cache_files) > target_count:
                # Sort by modification time (oldest first)
                cache_files.sort(key=lambda f: os.path.getmtime(f))
                
                # Delete oldest files
                files_to_delete = len(cache_files) - target_count
                for file_path in cache_files[:files_to_delete]:
                    try:
                        os.remove(file_path)
                        print(f"🗑 Removed old cache: {os.path.basename(file_path)}")
                    except Exception as e:
                        print(f"Warning: Could not delete cache file {file_path}: {e}")
        except Exception as e:
            print(f"Warning: Cache cleanup failed: {e}")
    
    def preview_internal_sound(self):
        """Extract and play internal CS2 sound using .NET Core decompiler"""
        if not self.selected_internal_sound:
            self.log("✗ No sound selected for preview")
            return
        
        # Try to use vsnd_decompiler with .NET Core
        if self.vsnd_decompiler:
            try:
                # Build paths
                vpk_path = os.path.join(self.cs2_basefolder, 'game', 'csgo', 'pak01_dir.vpk')
                # The selected sound is stored without extension, add .vsnd_c for VPK lookup
                internal_path = self.selected_internal_sound + '.vsnd_c'
                # Keep forward slashes for VPK (it uses forward slashes internally)
                internal_path = internal_path.replace('\\', '/')
                
                # Create cache directory
                cache_dir = os.path.join(tempfile.gettempdir(), '.CS2KZ-mapping-tools', 'sound_preview')
                os.makedirs(cache_dir, exist_ok=True)
                
                # Build output path
                sound_name = os.path.basename(self.selected_internal_sound)
                output_path = os.path.join(cache_dir, sound_name.replace('.vsnd', '.wav'))
                
                # Check if already cached
                if os.path.exists(output_path) or os.path.exists(output_path.replace('.wav', '.mp3')):
                    # Use cached version (update access time)
                    if os.path.exists(output_path):
                        os.utime(output_path, None)  # Touch file to update access time
                        self.play_sound_file(output_path)
                    else:
                        mp3_path = output_path.replace('.wav', '.mp3')
                        os.utime(mp3_path, None)
                        self.play_sound_file(mp3_path)
                    return
                
                # Clean up old cache files before adding new one (make room for the new file)
                self.cleanup_preview_cache(cache_dir, max_files=5, make_room_for_new=True)
                
                self.log(f"⏳ Decompiling {self.selected_internal_sound}...")
                
                # Decompile from VPK
                decompiled_path = self.vsnd_decompiler.decompile_vsnd(
                    vpk_path=vpk_path,
                    internal_sound_path=internal_path,
                    output_path=output_path
                )
                
                if decompiled_path and os.path.exists(decompiled_path):
                    self.play_sound_file(decompiled_path)
                else:
                    self.log("✗ Failed to decompile sound")
                    
            except Exception as e:
                self.log(f"✗ Error previewing sound: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Fallback message if decompiler not available
            self.log("ℹ Internal sound preview requires .NET Desktop Runtime 9.0")
            self.log("  The sound will work in-game when you click 'Add Sound'")
            self.log(f"  Selected: {self.selected_internal_sound}")
    
    
    def play_sound_file(self, file_path):
        """Play audio file using pygame with pitch adjustment"""
        try:
            # Reinitialize mixer to ensure clean state
            pygame.mixer.quit()
            
            # If pitch toggle is enabled and pitch != 1.0, adjust frequency
            # Standard frequency is 44100 Hz
            base_frequency = 44100
            
            if self.show_pitch and self.pitch != 1.0:
                # Change playback frequency to simulate pitch
                # Lower frequency = lower pitch, higher frequency = higher pitch
                # We need to load at normal rate but play at adjusted rate
                adjusted_frequency = int(base_frequency / self.pitch)
                # Clamp frequency to reasonable values (8000 Hz to 48000 Hz)
                adjusted_frequency = max(8000, min(48000, adjusted_frequency))
            else:
                adjusted_frequency = base_frequency
            
            pygame.mixer.init(frequency=adjusted_frequency, size=-16, channels=2, buffer=512)
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.set_volume(self.preview_volume)
            pygame.mixer.music.play()
            self.preview_playing = True
            
            if self.show_pitch and self.pitch != 1.0:
                self.log(f"♪ Playing: {os.path.basename(file_path)} (pitch: {self.pitch:.2f})")
            else:
                self.log(f"♪ Playing: {os.path.basename(file_path)}")
        except Exception as e:
            self.log(f"✗ Error playing sound: {e}")
            # Try to reinitialize mixer to default if there was an error
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
            except:
                pass
    
    def stop_sound(self):
        """Stop currently playing sound"""
        try:
            pygame.mixer.music.stop()
            self.preview_playing = False
            self.log("⏹ Stopped playback")
        except Exception as e:
            self.log(f"✗ Error stopping sound: {e}")
    
    def update_addon_filter(self, search_text):
        """Filter available addons based on search text"""
        if not search_text:
            self.filtered_addons = self.available_addons  # Show all when empty
        else:
            # Case-insensitive filter
            search_lower = search_text.lower()
            self.filtered_addons = [addon for addon in self.available_addons 
                                   if search_lower in addon.lower()]
        
        self.show_addon_dropdown = len(self.filtered_addons) > 0
        self.selected_addon_index = -1
    
    def log(self, message):
        """Add message to console output"""
        self.console_output.append(message)
        print(message)
    
    def browse_sound_file(self):
        """Open file dialog to select sound file"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        file_path = filedialog.askopenfilename(
            title="Select Sound File",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav"),
                ("MP3 Files", "*.mp3"),
                ("WAV Files", "*.wav"),
                ("All Files", "*.*")
            ]
        )
        root.destroy()
        
        if file_path:
            self.sound_file_path = file_path.replace("\\", "/")
            filename = os.path.basename(file_path)
            self.sound_file_display = filename
            # Extract sound name without extension
            self.sound_name = os.path.splitext(filename)[0]
            self.sound_status_color = (0.0, 1.0, 0.0, 1.0)  # Green
            self.log(f"✓ Selected: {self.sound_file_display}")
            self.log(f"  Sound name: {self.sound_name}")
        else:
            self.log("✗ No file selected")
    
    def add_sound(self):
        """Add the sound file to the addon folder and update soundevents file"""
        # Validate inputs
        if not self.addon_name.strip():
            self.log("✗ Error: Please enter an addon name")
            return
        
        if not self.cs2_basefolder:
            self.log("✗ Error: CS2 path not detected")
            return
        
        # Validate sound selection based on source
        if self.use_internal_sound:
            if not self.selected_internal_sound:
                self.log("✗ Error: Please select an internal sound")
                return
            if not self.sound_name.strip():
                self.log("✗ Error: Sound name is empty")
                return
        else:
            if not self.sound_file_path:
                self.log("✗ Error: Please select a sound file")
                return
            if not os.path.exists(self.sound_file_path):
                self.log("✗ Error: Selected sound file does not exist")
                return
        
        try:
            addon_name = self.addon_name.strip()
            
            # Handle custom file or internal sound differently
            if not self.use_internal_sound:
                # Custom file workflow (original behavior)
                # Construct the sounds folder path
                sounds_folder = os.path.join(
                    self.cs2_basefolder,
                    'content',
                    'csgo_addons',
                    addon_name,
                    'sounds'
                )
                
                # Create sounds folder if it doesn't exist
                os.makedirs(sounds_folder, exist_ok=True)
                self.log(f"✓ Content sounds folder: {sounds_folder}")
                
                # Copy the sound file (content root)
                dest_filename = os.path.basename(self.sound_file_path)
                dest_path = os.path.join(sounds_folder, dest_filename)
                shutil.copy2(self.sound_file_path, dest_path)
                self.log(f"✓ Content root file (.wav/.mp3): {dest_path}")
                
                # Compile the sound file directly (creates .vsnd_c in game root)
                if not self.compile_sound_file(dest_path):
                    self.log("✗ Warning: Sound file compilation failed, but content file was created")
                else:
                    # Calculate game root path where .vsnd_c will be
                    game_sounds_folder = os.path.join(
                        self.cs2_basefolder,
                        'game',
                        'csgo_addons',
                        addon_name,
                        'sounds'
                    )
                    vsnd_c_filename = os.path.splitext(dest_filename)[0] + ".vsnd_c"
                    vsnd_c_path = os.path.join(game_sounds_folder, vsnd_c_filename)
                    self.log(f"✓ Game root file (.vsnd_c): {vsnd_c_path}")
            else:
                # Internal sound workflow - just reference it, no copying needed
                self.log(f"✓ Using internal CS2 sound: {self.selected_internal_sound}")
            
            # Update soundevents_addon.vsndevts file
            soundevents_folder = os.path.join(
                self.cs2_basefolder,
                'content',
                'csgo_addons',
                addon_name,
                'soundevents'
            )
            os.makedirs(soundevents_folder, exist_ok=True)
            
            soundevents_file = os.path.join(soundevents_folder, 'soundevents_addon.vsndevts')
            
            # For custom files, pass the destination filename
            # For internal sounds, pass the internal sound path
            if self.use_internal_sound:
                self.update_soundevents_file(soundevents_file, None, self.selected_internal_sound)
            else:
                self.update_soundevents_file(soundevents_file, dest_filename, None)
            
            # Compile the soundevents file so Hammer can see it
            if not self.compile_sound_file(soundevents_file):
                self.log("✗ Warning: Soundevents file compilation failed")
            else:
                game_soundevents_folder = os.path.join(
                    self.cs2_basefolder,
                    'game',
                    'csgo_addons',
                    addon_name,
                    'soundevents'
                )
                soundevents_c_path = os.path.join(game_soundevents_folder, 'soundevents_addon.vsndevts_c')
                self.log(f"✓ Game soundevents file (.vsndevts_c): {soundevents_c_path}")
            
            self.log("✓ Sound added successfully!")
            
        except Exception as e:
            self.log(f"✗ Error adding sound: {e}")
            import traceback
            traceback.print_exc()
    
    def update_soundevents_file(self, soundevents_file, sound_filename=None, internal_sound_path=None):
        """Update or create the soundevents_addon.vsndevts file with new sound entry"""
        # Determine the vsnd reference based on whether it's custom or internal
        if internal_sound_path:
            # Internal sound - use the full path directly (already has .vsnd extension removed)
            vsnd_reference = internal_sound_path
        else:
            # Custom sound - convert filename to .vsnd reference in sounds/ folder
            vsnd_filename = os.path.splitext(sound_filename)[0] + ".vsnd"
            vsnd_reference = f"sounds/{vsnd_filename}"
        
        # Generate the soundevent entry
        soundevent_entry = f'''\t"{self.sound_name}" =
\t{{
\t\ttype = "{self.sound_type}"
\t\tvsnd_files_track_01 = "{vsnd_reference}"
\t\tvolume = {self.volume:.1f}
\t\tpitch = {self.pitch:.2f}
\t\tuse_distance_volume_mapping_curve = true
\t\tdistance_volume_mapping_curve = 
\t\t[
\t\t\t[{self.distance_near:.1f}, {self.distance_near_volume:.1f}, 0.0, 0.0, 2.0, 3.0,],
\t\t\t[{self.distance_mid:.1f}, {self.distance_mid_volume:.1f}, 0.0, 0.0, 2.0, 3.0],
\t\t\t[{self.distance_far:.1f}, {self.distance_far_volume:.1f}, 0.0, 0.0, 2.0, 3.0],
\t\t]
\t\tocclusion = {str(self.show_occlusion).lower()}
\t\tocclusion_intensity = {int(self.occlusion_intensity)}
\t}}
'''
        
        if os.path.exists(soundevents_file):
            # File exists, check if sound name already exists and remove it
            with open(soundevents_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove existing entry with the same name if it exists
            # Pattern to match the entire sound entry block
            pattern = rf'\t"{re.escape(self.sound_name)}"\s*=\s*\{{[^}}]*\}}\n?'
            content = re.sub(pattern, '', content, flags=re.DOTALL)
            
            # Find the last closing brace
            last_brace_index = content.rfind('}')
            if last_brace_index != -1:
                # Insert before the last closing brace
                new_content = content[:last_brace_index] + soundevent_entry + content[last_brace_index:]
            else:
                # Shouldn't happen, but append anyway
                new_content = content + soundevent_entry + '\n}'
            
            with open(soundevents_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.log(f"✓ Updated soundevents file (overwritten if existed): {soundevents_file}")
        else:
            # Create new file with header and soundevent
            header = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->
{
'''
            footer = '}\n'
            
            with open(soundevents_file, 'w', encoding='utf-8') as f:
                f.write(header + soundevent_entry + footer)
            
            self.log(f"✓ Created soundevents file: {soundevents_file}")
    
    def compile_sound_file(self, audio_file_path):
        """Compile a .wav/.mp3 file using resourcecompiler.exe to create .vsnd_c"""
        if not self.cs2_basefolder:
            self.log("✗ Error: CS2 path not detected")
            return False
        
        compiler_path = os.path.join(self.cs2_basefolder, 'game', 'bin', 'win64', 'resourcecompiler.exe')
        if not os.path.exists(compiler_path):
            self.log(f"✗ Error: resourcecompiler.exe not found at {compiler_path}")
            return False
        
        # Set the working directory for the compiler (should be the 'game' directory)
        compiler_cwd = os.path.join(self.cs2_basefolder, 'game')
        
        try:
            # The input file path needs to be relative to the 'game' directory
            relative_audio_path = os.path.relpath(audio_file_path, start=compiler_cwd).replace("\\", "/")
            
            self.log(f"Compiling {os.path.basename(audio_file_path)}...")
            
            command = [compiler_path, '-i', relative_audio_path]
            result = subprocess.run(command, cwd=compiler_cwd, check=True, capture_output=True, text=True)
            
            self.log(f"✓ Compilation successful for {os.path.basename(audio_file_path)}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"✗ Compilation failed for {os.path.basename(audio_file_path)}: {e}")
            self.log(f"Compiler stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            self.log(f"✗ Error: resourcecompiler.exe not found at {compiler_path}")
            return False
        except Exception as e:
            self.log(f"✗ Unexpected error during compilation: {e}")
            return False
    
    def open_addon_sounds_folder(self):
        """Open the addon sounds folder in Windows Explorer"""
        try:
            if not self.cs2_basefolder:
                self.log("✗ Error: CS2 path not detected")
                return
            
            if not self.addon_name.strip():
                self.log("✗ Error: Please enter an addon name")
                return
            
            sounds_folder = os.path.join(
                self.cs2_basefolder,
                'content',
                'csgo_addons',
                self.addon_name.strip(),
                'sounds'
            )
            
            if not os.path.exists(sounds_folder):
                os.makedirs(sounds_folder, exist_ok=True)
                self.log(f"✓ Created sounds folder: {sounds_folder}")
            
            os.startfile(sounds_folder)
            self.log(f"✓ Opened sounds folder")
            
        except Exception as e:
            self.log(f"✗ Error opening sounds folder: {e}")
    
    def init_window(self):
        """Initialize GLFW window and ImGui"""
        if not glfw.init():
            print("Could not initialize OpenGL context")
            sys.exit(1)
        
        # Scan for available addons after CS2 path is detected
        self.available_addons = self.scan_available_addons()
        self.update_addon_filter("")  # Initialize filtered list
        
        # Window hints
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)
        glfw.window_hint(glfw.DECORATED, glfw.FALSE)
        
        # Create window
        self.window = glfw.create_window(self.window_width, self.base_window_height, "CS2 Sounds Manager", None, None)
        if not self.window:
            glfw.terminate()
            print("Could not initialize Window")
            sys.exit(1)
        
        # Create cursors
        self.arrow_cursor = glfw.create_standard_cursor(glfw.ARROW_CURSOR)
        self.hand_cursor = glfw.create_standard_cursor(glfw.HAND_CURSOR)
        
        # Center window on screen
        monitor = glfw.get_primary_monitor()
        video_mode = glfw.get_video_mode(monitor)
        x_pos = (video_mode.size.width - self.window_width) // 2
        y_pos = (video_mode.size.height - self.base_window_height) // 2
        glfw.set_window_pos(self.window, x_pos, y_pos)
        
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)
        
        # Set window icon
        icon_path = resource_path(os.path.join("icons", "sounds.ico"))
        if os.path.exists(icon_path):
            try:
                icon_img = Image.open(icon_path)
                if icon_img.mode != 'RGBA':
                    icon_img = icon_img.convert('RGBA')
                
                try:
                    from glfw import _GLFWimage
                    img_buffer = icon_img.tobytes()
                    img = _GLFWimage()
                    img.width = icon_img.width
                    img.height = icon_img.height
                    img.pixels = img_buffer
                    glfw.set_window_icon(self.window, 1, img)
                except:
                    icon_data = icon_img.tobytes()
                    glfw.set_window_icon(self.window, 1, [[icon_img.width, icon_img.height, icon_data]])
            except:
                pass
        
        # Setup ImGui
        imgui.create_context()
        
        # Load font based on theme BEFORE creating renderer
        io = imgui.get_io()
        theme_name = self.theme_manager.get_theme_name()
        
        if theme_name == 'dracula':
            # Use Consolas for Dracula theme
            consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
            if os.path.exists(consolas_path):
                io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
            else:
                # Fallback to Roboto
                font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
                if os.path.exists(font_path):
                    io.fonts.add_font_from_file_ttf(font_path, 15.0)
        else:
            # Use Roboto for other themes
            font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
            if os.path.exists(font_path):
                io.fonts.add_font_from_file_ttf(font_path, 15.0)
        
        # Create renderer AFTER loading fonts
        self.impl = GlfwRenderer(self.window)
        
        # Apply theme colors to ImGui
        theme = self.theme_manager.get_theme()
        style = imgui.get_style()
        
        # Apply theme colors
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = theme['window_bg']
        style.colors[imgui.COLOR_BUTTON] = theme['button']
        style.colors[imgui.COLOR_BUTTON_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = theme['button_active']
        style.colors[imgui.COLOR_BORDER] = theme['border']
        style.colors[imgui.COLOR_TEXT] = theme['text']
        style.colors[imgui.COLOR_FRAME_BACKGROUND] = theme['button']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = theme['button_active']
        
        # Slider colors (match theme)
        style.colors[imgui.COLOR_SLIDER_GRAB] = theme['button_active']
        style.colors[imgui.COLOR_SLIDER_GRAB_ACTIVE] = theme['button_hover']
        
        # Checkbox colors (match theme)
        style.colors[imgui.COLOR_CHECK_MARK] = theme['button_active']
        
        # Style settings
        style.window_rounding = 0.0
        style.frame_rounding = 7.0
        style.window_padding = (14, 14)
        style.frame_padding = (10, 10)
        style.item_spacing = (7, 7)
        style.window_border_size = 0.0
        style.frame_border_size = 2.0
        style.scrollbar_size = 10.0  # Set to small value for child windows
        
        # Load title icon as texture
        self.load_title_icon()
    
    def load_title_icon(self):
        """Load title icon as OpenGL texture"""
        icon_path = resource_path(os.path.join("icons", "sounds.ico"))
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                img = img.resize((16, 16), Image.Resampling.LANCZOS)
                width, height = img.size
                img_data = img.tobytes()
                
                # Create OpenGL texture
                texture = gl.glGenTextures(1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height,
                               0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data)
                
                self.title_icon = texture
            except Exception as e:
                print(f"Failed to load title icon: {e}")
    
    def render_title_bar(self):
        """Render custom title bar"""
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(self.window_width, CUSTOM_TITLE_BAR_HEIGHT)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        
        # Darker title bar
        theme = self.theme_manager.get_theme()
        r, g, b, a = theme['window_bg']
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
        if self.title_icon:
            imgui.image(self.title_icon, 16, 16)
            imgui.same_line(spacing=4)
        
        # Title text with theme color
        theme = self.theme_manager.get_theme()
        text_color = theme['text']
        imgui.push_style_color(imgui.COLOR_TEXT, *text_color)
        imgui.text("CS2 Sounds Manager")
        imgui.pop_style_color(1)
        
        # Get the position for the buttons (right side)
        button_size = 20
        button_spacing = 4
        total_button_width = (button_size * 2) + button_spacing  # Minimize + Close
        
        imgui.same_line(self.window_width - total_button_width - 6)
        
        # VS Code style buttons - flat, no borders when not hovered
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 0.0)
        
        # Minimize button (VS Code style)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)  # Transparent
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.2, 0.2, 0.2, 1.0)  # Dark gray
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)  # No border
        
        minimize_clicked = imgui.button("##minimize", width=button_size, height=button_size)
        
        # Draw centered minimize symbol manually
        min_button_min = imgui.get_item_rect_min()
        draw_list = imgui.get_window_draw_list()
        
        # Draw a centered horizontal line for minimize
        line_width = 8
        line_height = 1
        line_x = min_button_min.x + (button_size - line_width) // 2
        line_y = min_button_min.y + (button_size - line_height) // 2
        line_color = imgui.get_color_u32_rgba(0.8, 0.8, 0.8, 1.0)
        draw_list.add_rect_filled(line_x, line_y, line_x + line_width, line_y + line_height + 1, line_color)
        
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
        
        # Draw centered X symbol manually
        close_button_min = imgui.get_item_rect_min()
        
        # Calculate center of button
        center_x = close_button_min.x + button_size // 2
        center_y = close_button_min.y + button_size // 2
        
        # Draw X with two lines
        x_size = 6
        text_color = imgui.get_color_u32_rgba(0.8, 0.8, 0.8, 1.0)
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
        
        # Handle window dragging
        if imgui.is_window_hovered() and imgui.is_mouse_clicked(0):
            self.dragging_window = True
            mouse_x, mouse_y = glfw.get_cursor_pos(self.window)
            win_x, win_y = glfw.get_window_pos(self.window)
            self.drag_offset_x = mouse_x
            self.drag_offset_y = mouse_y
        
        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(3)
    
    def render_main_window(self):
        """Render main application window with two-panel layout"""
        # Left Panel - File Selection (leave room for bottom button bar)
        button_bar_height = 60
        imgui.set_next_window_position(0, CUSTOM_TITLE_BAR_HEIGHT)
        imgui.set_next_window_size(self.left_panel_width, self.base_window_height - CUSTOM_TITLE_BAR_HEIGHT - button_bar_height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (14, 14))
        
        flags = (
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_COLLAPSE
        )
        
        imgui.begin("##left_panel", flags=flags)
        
        # === Addon Name Section ===
        imgui.text("Addon Name:")
        imgui.push_item_width(-1)
        
        # If addon was just selected, the value has already been updated in self.addon_name
        # ImGui's input_text will pick up the new value on this frame
        if self.addon_just_selected:
            print(f"DEBUG: Addon just selected, current value: '{self.addon_name}'")
            self.addon_just_selected = False
        
        changed, new_value = imgui.input_text(
            "##addon_name",
            self.addon_name,
            256
        )
        if changed:
            print(f"DEBUG: Input changed from '{self.addon_name}' to '{new_value}'")
            self.addon_name = new_value
            # Update filtered addons when user types
            self.update_addon_filter(new_value)
        
        # Track if input is focused
        is_focused = imgui.is_item_focused()
        
        # Don't immediately hide dropdown when losing focus - give time for button click to register
        # Only show dropdown when input is focused
        # (Dropdown will close itself when a selection is made)
        # Check if input is focused and Enter is pressed
        if is_focused:
            # Handle arrow keys for dropdown navigation
            if self.show_addon_dropdown and len(self.filtered_addons) > 0:
                if imgui.is_key_pressed(imgui.KEY_DOWN_ARROW):
                    self.selected_addon_index = min(self.selected_addon_index + 1, len(self.filtered_addons) - 1)
                elif imgui.is_key_pressed(imgui.KEY_UP_ARROW):
                    self.selected_addon_index = max(self.selected_addon_index - 1, -1)
                elif imgui.is_key_pressed(imgui.KEY_ENTER) and self.selected_addon_index >= 0:
                    # Select the addon
                    self.addon_name = self.filtered_addons[self.selected_addon_index]
                    self.show_addon_dropdown = False
                    self.selected_addon_index = -1
                elif imgui.is_key_pressed(imgui.KEY_ESCAPE):
                    self.show_addon_dropdown = False
                    self.selected_addon_index = -1
        
        imgui.pop_item_width()
        
        # Show dropdown with available addons
        if self.show_addon_dropdown and len(self.filtered_addons) > 0:
            # Get current theme colors
            theme = self.theme_manager.get_theme()
            
            # Use theme colors for dropdown
            imgui.push_style_color(imgui.COLOR_CHILD_BACKGROUND, *theme['window_bg'])
            imgui.push_style_color(imgui.COLOR_BORDER, *theme['border'])
            imgui.push_style_var(imgui.STYLE_CHILD_ROUNDING, 4.0)
            imgui.push_style_var(imgui.STYLE_CHILD_BORDERSIZE, 1.0)
            
            # Calculate dropdown height
            item_height = 30  # Height per item
            num_items = len(self.filtered_addons)
            
            # If 5 or fewer items, show them all without scrollbar
            # Otherwise, show max 8 items with scrollbar
            if num_items <= 5:
                # Show exact height for all items (no scrollbar)
                # Add extra pixels to account for padding/borders/spacing
                dropdown_height = (num_items * item_height) + 45
            else:
                # Show max 8 items with scrollbar
                max_visible_items = 8
                dropdown_height = (max_visible_items * item_height) + 45
            
            dropdown_width = max(self.left_panel_width - 28, 100)  # Ensure minimum width
            
            imgui.begin_child("##addon_dropdown", dropdown_width, dropdown_height, border=True)
            
            for i, addon in enumerate(self.filtered_addons):
                is_selected = (i == self.selected_addon_index)
                
                # Highlight selected item with theme colors
                if is_selected:
                    imgui.push_style_color(imgui.COLOR_BUTTON, *theme['button_active'])
                else:
                    imgui.push_style_color(imgui.COLOR_BUTTON, *theme['button'])
                
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *theme['button_hover'])
                imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *theme['button_active'])
                
                if imgui.button(addon, width=-1, height=item_height):
                    print(f"DEBUG: Selected addon: '{addon}'")
                    self.addon_name = addon
                    print(f"DEBUG: self.addon_name set to: '{self.addon_name}'")
                    self.show_addon_dropdown = False
                    self.selected_addon_index = -1
                    # Clear the filter since we selected something
                    self.filtered_addons = []
                    self.addon_just_selected = True  # Flag to force input update next frame
                
                imgui.pop_style_color(3)
            
            imgui.end_child()
            imgui.pop_style_var(2)
            imgui.pop_style_color(2)
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # === Sound Source Selection ===
        imgui.text("Sound Source:")
        imgui.spacing()
        
        # Radio buttons for custom file vs internal sound
        if imgui.radio_button("Custom Sound", not self.use_internal_sound):
            self.use_internal_sound = False
        
        imgui.same_line()
        if imgui.radio_button("CS2 Sounds", self.use_internal_sound):
            self.use_internal_sound = True
            # Load internal sounds on first use
            if not self.internal_sounds_loaded and not self.loading_internal_sounds:
                self.load_internal_sounds()
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # === Sound File/Internal Sound Selection ===
        if not self.use_internal_sound:
            # Custom file browser
            imgui.text("Sound File:")
            
            # File path display with color
            imgui.push_style_color(imgui.COLOR_TEXT, *self.sound_status_color)
            # Wrap text to fit in narrow panel
            imgui.push_text_wrap_pos(self.left_panel_width - 28)
            imgui.text(self.sound_file_display)
            imgui.pop_text_wrap_pos()
            imgui.pop_style_color(1)
            
            imgui.spacing()
            
            # Browse button
            if imgui.button("Browse Sound", width=-1, height=30):
                self.browse_sound_file()
            
            # Preview controls for custom sounds
            if self.sound_file_path:
                imgui.spacing()
                imgui.separator()
                imgui.spacing()
                
                # Preview button
                if imgui.button("Preview Sound", width=-1, height=25):
                    self.play_sound_file(self.sound_file_path)
                
                imgui.spacing()
                
                imgui.text("Preview Volume:")
                imgui.spacing()
                
                # Volume slider
                changed, self.preview_volume = imgui.slider_float(
                    "##preview_vol", 
                    self.preview_volume, 
                    0.0, 
                    1.0, 
                    "%.2f"
                )
                if changed:
                    pygame.mixer.music.set_volume(self.preview_volume)
                
                imgui.spacing()
                
                # Stop button
                if imgui.button("Stop Preview", width=-1, height=25):
                    self.stop_sound()
        else:
            # Internal sound browser
            imgui.text("Search:")
            
            if self.loading_internal_sounds:
                imgui.text_colored("Loading...", 1.0, 1.0, 0.0)
            elif not self.internal_sounds_loaded:
                imgui.text_colored("Click 'Load Sounds' to browse", 1.0, 0.5, 0.0)
                if imgui.button("Load Sounds", width=-1, height=30):
                    self.load_internal_sounds()
            else:
                # Get current theme colors
                theme = self.theme_manager.get_theme()
                
                # Filter input
                changed, self.internal_sound_filter = imgui.input_text("##internal_filter", self.internal_sound_filter, 256)
                if changed:
                    self.filter_internal_sounds(self.internal_sound_filter)
                
                imgui.spacing()
                
                # Sound list in scrollable child window (reduced height to 250)
                imgui.begin_child("##internal_sounds_list", 0, 250, border=True)
                
                for sound in self.filtered_internal_sounds[:500]:  # Limit display to 500 for performance
                    is_selected = (sound == self.selected_internal_sound)
                    
                    # Extract just the filename (without path and extension)
                    display_name = os.path.basename(sound)
                    
                    # Apply theme colors for hover and active states
                    imgui.push_style_color(imgui.COLOR_HEADER_HOVERED, *theme['button_hover'])
                    imgui.push_style_color(imgui.COLOR_HEADER_ACTIVE, *theme['button_active'])
                    
                    if is_selected:
                        imgui.push_style_color(imgui.COLOR_HEADER, *theme['button_active'])
                    else:
                        imgui.push_style_color(imgui.COLOR_HEADER, *theme['button'])
                    
                    # Use selectable for better performance, show only filename
                    clicked, _ = imgui.selectable(display_name, is_selected)
                    if clicked:
                        self.selected_internal_sound = sound
                        self.sound_name = display_name
                        # Auto-preview when clicking
                        self.preview_internal_sound()
                    
                    imgui.pop_style_color(3)
                
                imgui.end_child()
                
                # Show selected sound (also just filename)
                if self.selected_internal_sound:
                    imgui.spacing()
                    imgui.text_colored("Selected:", 0.0, 1.0, 0.0)
                    imgui.push_text_wrap_pos(self.left_panel_width - 28)
                    imgui.text(os.path.basename(self.selected_internal_sound))
                    imgui.pop_text_wrap_pos()
                
                # === Preview Controls (moved here, right after sound list) ===
                imgui.spacing()
                imgui.separator()
                imgui.spacing()
                
                imgui.text("Preview Volume:")
                imgui.spacing()
                
                # Volume slider
                changed, self.preview_volume = imgui.slider_float(
                    "##preview_vol", 
                    self.preview_volume, 
                    0.0, 
                    1.0, 
                    "%.2f"
                )
                if changed:
                    pygame.mixer.music.set_volume(self.preview_volume)
                
                imgui.spacing()
                
                # Stop button
                if imgui.button("Stop Preview", width=-1, height=25):
                    self.stop_sound()
        
        imgui.end()
        imgui.pop_style_var(2)
        
        # Right Panel - Sound Settings (leave room for bottom button bar)
        button_bar_height = 60
        imgui.set_next_window_position(self.left_panel_width, CUSTOM_TITLE_BAR_HEIGHT)
        imgui.set_next_window_size(self.right_panel_width, self.base_window_height - CUSTOM_TITLE_BAR_HEIGHT - button_bar_height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (14, 14))
        
        imgui.begin("##right_panel", flags=flags)
        
        content_start_y = imgui.get_cursor_pos_y()
        
        # === Toggle Buttons (moved to top of right panel) ===
        imgui.text("Show Parameters:")
        imgui.spacing()
        
        changed, self.show_pitch = imgui.checkbox("Pitch", self.show_pitch)
        imgui.same_line()
        changed, self.show_occlusion = imgui.checkbox("Occlusion", self.show_occlusion)
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        imgui.text("Sound Settings")
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # Sound Type selection
        imgui.text("Sound Type:")
        imgui.spacing()
        
        # Enable text wrapping for descriptions
        imgui.push_text_wrap_pos(self.right_panel_width - 20)
        
        if imgui.radio_button("csgo_mega", self.sound_type == "csgo_mega"):
            self.sound_type = "csgo_mega"
        imgui.same_line()
        imgui.text_colored("- Used for the majority of sounds", 0.6, 0.6, 0.6, 1.0)
        
        if imgui.radio_button("csgo_music", self.sound_type == "csgo_music"):
            self.sound_type = "csgo_music"
        imgui.same_line()
        imgui.text_colored("- Used for music. Volume affected by snd_musicvolume", 0.6, 0.6, 0.6, 1.0)
        
        if imgui.radio_button("csgo_3d", self.sound_type == "csgo_3d"):
            self.sound_type = "csgo_3d"
        imgui.same_line()
        imgui.text_colored("- General ambient noises", 0.6, 0.6, 0.6, 1.0)
        
        imgui.pop_text_wrap_pos()
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # Volume slider
        imgui.text("Volume:")
        imgui.push_item_width(-1)
        changed, self.volume = imgui.slider_float("##volume", self.volume, 0.0, 10.0, "%.1f")
        imgui.pop_item_width()
        imgui.spacing()
        
        # Pitch slider (conditional)
        if self.show_pitch:
            imgui.text("Pitch:")
            imgui.push_item_width(-1)
            changed, self.pitch = imgui.slider_float("##pitch", self.pitch, 0.1, 3.0, "%.2f")
            imgui.pop_item_width()
            imgui.spacing()
        
        # Occlusion slider (conditional, moved under pitch)
        if self.show_occlusion:
            imgui.text("Occlusion Intensity:")
            imgui.push_item_width(-1)
            changed, self.occlusion_intensity = imgui.slider_float("##occlusion", self.occlusion_intensity, 0.0, 100.0, "%.0f")
            imgui.pop_item_width()
            imgui.spacing()
        
        imgui.text("Distance Volume Curve")
        imgui.spacing()
        
        # Column widths
        distance_col_width = 220
        volume_col_width = 220
        
        # Near distance settings (side by side)
        imgui.columns(2, "near_columns", False)
        imgui.set_column_width(0, distance_col_width)
        imgui.set_column_width(1, volume_col_width)
        
        imgui.text("Near Distance (units):")
        imgui.push_item_width(-1)
        changed, self.distance_near = imgui.slider_float("##dist_near", self.distance_near, 0.0, 10000.0, "%.0f")
        imgui.pop_item_width()
        
        imgui.next_column()
        
        imgui.text("Near Volume:")
        imgui.push_item_width(-1)
        changed, self.distance_near_volume = imgui.slider_float("##vol_near", self.distance_near_volume, 0.0, 1.0, "%.1f")
        imgui.pop_item_width()
        
        imgui.columns(1)
        imgui.spacing()
        
        # Mid distance settings (side by side)
        imgui.columns(2, "mid_columns", False)
        imgui.set_column_width(0, distance_col_width)
        imgui.set_column_width(1, volume_col_width)
        
        imgui.text("Mid Distance (units):")
        imgui.push_item_width(-1)
        changed, self.distance_mid = imgui.slider_float("##dist_mid", self.distance_mid, 0.0, 10000.0, "%.0f")
        imgui.pop_item_width()
        
        imgui.next_column()
        
        imgui.text("Mid Volume:")
        imgui.push_item_width(-1)
        changed, self.distance_mid_volume = imgui.slider_float("##vol_mid", self.distance_mid_volume, 0.0, 1.0, "%.1f")
        imgui.pop_item_width()
        
        imgui.columns(1)
        imgui.spacing()
        
        # Far distance settings (side by side)
        imgui.columns(2, "far_columns", False)
        imgui.set_column_width(0, distance_col_width)
        imgui.set_column_width(1, volume_col_width)
        
        imgui.text("Far Distance (units):")
        imgui.push_item_width(-1)
        changed, self.distance_far = imgui.slider_float("##dist_far", self.distance_far, 0.0, 10000.0, "%.0f")
        imgui.pop_item_width()
        
        imgui.next_column()
        
        imgui.text("Far Volume:")
        imgui.push_item_width(-1)
        changed, self.distance_far_volume = imgui.slider_float("##vol_far", self.distance_far_volume, 0.0, 1.0, "%.1f")
        imgui.pop_item_width()
        
        imgui.columns(1)
        imgui.spacing()
        
        # Calculate actual content height and adjust window if needed
        content_end_y = imgui.get_cursor_pos_y()
        calculated_content_height = content_end_y - content_start_y
        
        # Add padding
        style = imgui.get_style()
        total_content_height = calculated_content_height + (style.window_padding.y * 2)
        
        # Check if we need to resize window (add title bar height + button bar height)
        button_bar_height = 60
        desired_window_height = int(CUSTOM_TITLE_BAR_HEIGHT + total_content_height + button_bar_height + 20)  # +20 for safety margin
        if abs(desired_window_height - self.base_window_height) > 10:
            self.base_window_height = desired_window_height
            glfw.set_window_size(self.window, self.window_width, self.base_window_height)
        
        imgui.end()
        imgui.pop_style_var(2)
        
        # Bottom action buttons bar (spanning full window width)
        button_bar_height = 60
        imgui.set_next_window_position(0, self.base_window_height - button_bar_height)
        imgui.set_next_window_size(self.window_width, button_bar_height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (14, 10))
        
        imgui.begin("##bottom_bar", flags=flags)
        
        # Calculate button widths
        button_width = 150
        button_spacing = 10
        total_button_width = (button_width * 2) + button_spacing
        
        # Position buttons on the right side
        imgui.set_cursor_pos_x(self.window_width - total_button_width - 14)
        
        # Open Folder button (Yellow)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.8, 0.7, 0.2, 1.0)  # Yellow
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.9, 0.8, 0.3, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.7, 0.6, 0.15, 1.0)
        
        if imgui.button("Open Folder", width=button_width, height=40):
            self.open_addon_sounds_folder()
        
        imgui.pop_style_color(3)
        
        imgui.same_line(spacing=button_spacing)
        
        # Add Sound button (Green)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.7, 0.3, 1.0)  # Green
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.8, 0.4, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.6, 0.25, 1.0)
        
        if imgui.button("Add Sound", width=button_width, height=40):
            self.add_sound()
        
        imgui.pop_style_color(3)
        
        imgui.end()
        imgui.pop_style_var(2)
    
    def reapply_theme(self):
        """Reapply theme colors when theme changes"""
        theme = self.theme_manager.get_theme()
        style = imgui.get_style()
        
        # Apply theme colors
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = theme['window_bg']
        style.colors[imgui.COLOR_BUTTON] = theme['button']
        style.colors[imgui.COLOR_BUTTON_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = theme['button_active']
        style.colors[imgui.COLOR_BORDER] = theme['border']
        style.colors[imgui.COLOR_TEXT] = theme['text']
        style.colors[imgui.COLOR_FRAME_BACKGROUND] = theme['button']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = theme['button_active']
        
        # Slider colors (match theme)
        style.colors[imgui.COLOR_SLIDER_GRAB] = theme['button_active']
        style.colors[imgui.COLOR_SLIDER_GRAB_ACTIVE] = theme['button_hover']
        
        # Checkbox colors (match theme)
        style.colors[imgui.COLOR_CHECK_MARK] = theme['button_active']
        
        # Check if we need to reload font (Dracula uses different font)
        new_theme_name = self.theme_manager.get_theme_name()
        old_was_dracula = self.current_theme_name == 'dracula'
        new_is_dracula = new_theme_name == 'dracula'
        
        if old_was_dracula != new_is_dracula:
            # Theme switched between Dracula and other themes, need to reload font
            io = imgui.get_io()
            io.fonts.clear()
            
            if new_is_dracula:
                # Load Consolas for Dracula
                consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
                if os.path.exists(consolas_path):
                    io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
                else:
                    # Fallback to Roboto
                    font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
                    if os.path.exists(font_path):
                        io.fonts.add_font_from_file_ttf(font_path, 15.0)
            else:
                # Load Roboto for other themes
                font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
                if os.path.exists(font_path):
                    io.fonts.add_font_from_file_ttf(font_path, 15.0)
            
            # Rebuild font atlas
            self.impl.refresh_font_texture()
        
        self.current_theme_name = new_theme_name
    
    def run(self):
        """Main application loop"""
        self.init_window()
        
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.impl.process_inputs()
            
            # Check for theme updates
            if self.theme_manager.check_for_updates():
                self.reapply_theme()
            
            # Handle window dragging
            if self.dragging_window:
                if glfw.get_mouse_button(self.window, glfw.MOUSE_BUTTON_LEFT) == glfw.PRESS:
                    mouse_x, mouse_y = glfw.get_cursor_pos(self.window)
                    win_x, win_y = glfw.get_window_pos(self.window)
                    new_x = int(win_x + mouse_x - self.drag_offset_x)
                    new_y = int(win_y + mouse_y - self.drag_offset_y)
                    glfw.set_window_pos(self.window, new_x, new_y)
                else:
                    self.dragging_window = False
            
            imgui.new_frame()
            
            self.render_title_bar()
            self.render_main_window()
            
            # Set cursor to pointer when hovering over clickable items
            if imgui.is_any_item_hovered():
                glfw.set_cursor(self.window, self.hand_cursor)
            else:
                glfw.set_cursor(self.window, self.arrow_cursor)
            
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            
            imgui.render()
            self.impl.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)
        
        self.impl.shutdown()
        glfw.terminate()


if __name__ == '__main__':
    app = SoundsManagerApp()
    app.run()
