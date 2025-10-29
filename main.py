"""
PyImGui version of CS2KZ Mapping Tools
Full-featured version with all capabilities from the original
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
from scripts.settings_manager import SettingsManager

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
WINDOW_WIDTH = 259  # Fixed width for 2 columns: 14 + 112 + 7 + 112 + 14 = 259
WINDOW_WIDTH_COMPACT = 240  # Width for single column: increased for checkmark space
CUSTOM_TITLE_BAR_HEIGHT = 30  # Custom title bar height
MENU_BAR_HEIGHT = 0
TOP_PADDING = 0  # Padding above buttons - customize this value
BUTTON_SIZE = 112
BUTTON_SIZE_COMPACT_WIDTH = 212  # Wider button for compact mode (240 - 14 - 14 = 212)
BUTTON_SIZE_COMPACT_HEIGHT = 40  # Shorter button for compact mode
BUTTON_SPACING = 7
ROW_HEIGHT = BUTTON_SIZE + BUTTON_SPACING  # Space for button + spacing between rows
ROW_HEIGHT_COMPACT = BUTTON_SIZE_COMPACT_HEIGHT + BUTTON_SPACING  # Space for compact buttons
BOTTOM_PADDING = 55  # Padding below buttons - customize this value
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
            "dedicated_server": saved_visibility.get("dedicated_server", True),
            "insecure": saved_visibility.get("insecure", True),
            "listen": saved_visibility.get("listen", True),
            "mapping": saved_visibility.get("mapping", True),
            "source2viewer": saved_visibility.get("source2viewer", True),
            "cs2importer": saved_visibility.get("cs2importer", True),
            "skyboxconverter": saved_visibility.get("skyboxconverter", True),
            "vtf2png": saved_visibility.get("vtf2png", True),
            "loading_screen": saved_visibility.get("loading_screen", True),
            "point_worldtext": saved_visibility.get("point_worldtext", True)
        }
        
        # Button order from settings
        self.button_order = self.settings.get_button_order()
        
        # Settings from settings manager
        self.show_move_icons = self.settings.get('show_move_icons', False)
        self.auto_update_source2viewer = self.settings.get('auto_update_source2viewer', True)
        self.auto_update_metamod = self.settings.get('auto_update_metamod', True)
        self.auto_update_cs2kz = self.settings.get('auto_update_cs2kz', True)
        self.compact_mode = self.settings.get('compact_mode', True)
        appearance = self.settings.get('appearance_mode', 'dark')
        self.dark_mode = appearance == 'dark' or appearance == 'system'
        
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
        
        # Cursor state
        self.current_cursor = None
        self.should_show_hand = False
    
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
                "dedicated_server": True,
                "insecure": True,
                "listen": True,
                "mapping": True,
                "source2viewer": True,
                "cs2importer": True,
                "skyboxconverter": True,
                "vtf2png": True,
                "loading_screen": True,
                "point_worldtext": True
            }
            self.button_order = ['mapping', 'listen', 'dedicated_server', 'insecure', 'source2viewer', 'cs2importer', 'skyboxconverter', 'loading_screen', 'point_worldtext', 'vtf2png']
            self.show_move_icons = False
            self.auto_update_source2viewer = True
            self.auto_update_metamod = True
            self.auto_update_cs2kz = True
            self.compact_mode = True
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
    
    def clear_pointworldtext_cache(self):
        """Clear Point Worldtext temporary character images"""
        import tempfile
        temp_dir = tempfile.gettempdir()
        app_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
        
        # Files to keep (don't delete)
        keep_files = {'settings.json', 'Source2Viewer.exe', 'ValveResourceFormat.xml'}
        
        try:
            if os.path.exists(app_dir):
                # Remove all files in the directory except protected files
                files_removed = 0
                for filename in os.listdir(app_dir):
                    if filename not in keep_files:
                        file_path = os.path.join(app_dir, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                files_removed += 1
                        except Exception as e:
                            print(f"Error removing {filename}: {e}")
                print(f"Point Worldtext cache cleared: {files_removed} files removed")
            else:
                print("No Point Worldtext cache found")
        except Exception as e:
            print(f"Error clearing Point Worldtext cache: {e}")
    
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
        
        # Get Source2Viewer path
        s2v_path = os.path.join(app_dir, 'Source2Viewer.exe')
        
        tooltips = {
            "mapping": f"Launches CS2 Hammer Editor with the latest Metamod, CS2KZ and Mapping API versions. (insecure)\n\nInstalled versions:\nMetamod: {versions.get('metamod', 'Not installed')}\nCS2KZ: {versions.get('cs2kz', 'Not installed')}",
            
            "listen": f"Launches CS2 with the latest Metamod, CS2KZ and Mapping API versions. (insecure)\n\nInstalled versions:\nMetamod: {versions.get('metamod', 'Not installed')}\nCS2KZ: {versions.get('cs2kz', 'Not installed')}",
            
            "dedicated_server": f"Launches a CS2 Dedicated Server with the latest Metamod, CS2KZ and Mapping API versions. (insecure)\n\nInstalled versions:\nMetamod: {versions.get('metamod', 'Not installed')}\nCS2KZ: {versions.get('cs2kz', 'Not installed')}",
            
            "insecure": "Launches CS2 in insecure mode.",
            
            "source2viewer": (f"Launches Source2Viewer with the latest dev build. (Updates may take some time)\n\nInstalls to: {s2v_path}", True),  # Tuple: (text, has_orange)

            "cs2importer": "Port CS:GO maps to CS2 with the best tool around.\n\nInspired by:\nsarim-hk\nandreaskeller96",

            "skyboxconverter": "Automate the converting of (CS:GO etc...) cubemap skyboxes to a CS2 compatible format.",
            
            "loading_screen": "Automate the adding of Loading Screen Images, Map Icons and Descriptions.",
            
            "point_worldtext": "Create CS:GO style point_worldtext png images.",
            
            "vtf2png": "Convert CS:GO vtf files to png images."
        }
        
        result = tooltips.get(name, "")
        # Return just the text if it's a tuple, otherwise return as-is
        if isinstance(result, tuple):
            return result[0]
        return result
    
    def calculate_window_height(self):
        """Calculate window height based on number of visible buttons"""
        visible_count = sum(1 for v in self.button_visibility.values() if v)
        if self.compact_mode:
            # Single column, one button per row
            num_rows = visible_count if visible_count > 0 else 1
            return CUSTOM_TITLE_BAR_HEIGHT + MENU_BAR_HEIGHT + TOP_PADDING + (num_rows * ROW_HEIGHT_COMPACT) + BOTTOM_PADDING
        else:
            # 2 columns
            num_rows = (visible_count + 1) // 2 if visible_count > 0 else 1
            return CUSTOM_TITLE_BAR_HEIGHT + MENU_BAR_HEIGHT + TOP_PADDING + (num_rows * ROW_HEIGHT) + BOTTOM_PADDING
    
    def get_window_width(self):
        """Get window width based on compact mode"""
        return WINDOW_WIDTH_COMPACT if self.compact_mode else WINDOW_WIDTH
    
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
        
        # Set window icon (using pyGLFW's internal structure)
        icon_path = resource_path(os.path.join("icons", "hammerkz.ico"))
        if os.path.exists(icon_path):
            try:
                import ctypes
                icon_img = Image.open(icon_path)
                icon_img = icon_img.convert("RGBA")
                width, height = icon_img.size
                pixels = icon_img.tobytes()
                
                # Create a simple object to hold the image data
                class GLFWimage(ctypes.Structure):
                    _fields_ = [
                        ('width', ctypes.c_int),
                        ('height', ctypes.c_int),
                        ('pixels', ctypes.POINTER(ctypes.c_ubyte))
                    ]
                
                # Convert pixels to ctypes array
                pixel_data = (ctypes.c_ubyte * len(pixels)).from_buffer_bytearray(bytearray(pixels))
                
                image = GLFWimage()
                image.width = width
                image.height = height
                image.pixels = ctypes.cast(pixel_data, ctypes.POINTER(ctypes.c_ubyte))
                
                glfw.set_window_icon(self.window, 1, [image])
            except Exception as e:
                # Silently fail - icon is nice to have but not critical
                pass
        
        # Setup ImGui
        imgui.create_context()
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
        
        # Enable font with better rendering
        io.font_global_scale = 1.0
        
        if self.dark_mode:
            imgui.style_colors_dark()
            # Match CustomTkinter dark theme
            style.colors[imgui.COLOR_WINDOW_BACKGROUND] = (0.1, 0.1, 0.1, 1.0)
            style.colors[imgui.COLOR_MENUBAR_BACKGROUND] = (0.16, 0.16, 0.16, 1.0)
            style.colors[imgui.COLOR_BUTTON] = (0.29, 0.29, 0.29, 1.0)  # gray25
            style.colors[imgui.COLOR_BUTTON_HOVERED] = (0.35, 0.35, 0.35, 1.0)  # gray30
            style.colors[imgui.COLOR_BUTTON_ACTIVE] = (0.40, 0.40, 0.40, 1.0)
            style.colors[imgui.COLOR_BORDER] = (0.40, 0.40, 0.40, 1.0)  # gray40
            style.colors[imgui.COLOR_TEXT] = (1.0, 1.0, 1.0, 1.0)
            # Menu items hover (match button hover)
            style.colors[imgui.COLOR_HEADER_HOVERED] = (0.35, 0.35, 0.35, 1.0)  # Same as button hover
            style.colors[imgui.COLOR_HEADER_ACTIVE] = (0.40, 0.40, 0.40, 1.0)
        else:
            imgui.style_colors_light()
            # Match CustomTkinter light theme
            style.colors[imgui.COLOR_WINDOW_BACKGROUND] = (0.94, 0.94, 0.94, 1.0)
            style.colors[imgui.COLOR_MENUBAR_BACKGROUND] = (0.88, 0.88, 0.88, 1.0)
            style.colors[imgui.COLOR_BUTTON] = (0.75, 0.75, 0.75, 1.0)  # gray75
            style.colors[imgui.COLOR_BUTTON_HOVERED] = (0.70, 0.70, 0.70, 1.0)  # gray70
            style.colors[imgui.COLOR_BUTTON_ACTIVE] = (0.65, 0.65, 0.65, 1.0)
            style.colors[imgui.COLOR_BORDER] = (0.60, 0.60, 0.60, 1.0)  # gray60
            style.colors[imgui.COLOR_TEXT] = (0.1, 0.1, 0.1, 1.0)
            # Menu items hover (match button hover)
            style.colors[imgui.COLOR_HEADER_HOVERED] = (0.70, 0.70, 0.70, 1.0)  # Same as button hover
            style.colors[imgui.COLOR_HEADER_ACTIVE] = (0.65, 0.65, 0.65, 1.0)
        
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
            "title_icon": "hammerkz.ico"  # Icon for title bar
        }
        
        for name, filename in icons.items():
            path = resource_path(os.path.join("icons", filename))
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    # Ensure RGBA mode
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    # Use smaller size for title icon
                    if name == "title_icon":
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
        else:
            button_width = BUTTON_SIZE
            button_height = BUTTON_SIZE
            icon_size = 56
        
        # If disabled, push grayed-out style
        if is_disabled:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.2, 0.2, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.2, 0.2, 0.2, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.2, 0.2, 0.2, 1.0)
        
        # Button with fixed size (matching CustomTkinter)
        button_pressed = imgui.button(f"##{name}", width=button_width, height=button_height)
        is_hovered = imgui.is_item_hovered()
        
        # Show hand cursor on hover
        if is_hovered:
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)
        
        # Show tooltip on hover
        if is_hovered:
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
            else:
                # Normal mode: icon on top, text below
                # Draw icon if available
                if icon_key and icon_key in self.button_icons:
                    texture = self.button_icons[icon_key]
                    icon_x = button_min.x + (button_width - icon_size) // 2
                    icon_y = button_min.y + 15
                    
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
                    
                    # Draw text below icon
                    text_y = icon_y + icon_size + 8
                else:
                    # No icon, center text vertically
                    text_y = button_min.y + 45
                
                # Draw button label (centered) - grayed out if disabled
                if is_disabled:
                    text_color = imgui.get_color_u32_rgba(0.4, 0.4, 0.4, 1)
                else:
                    text_color = imgui.get_color_u32_rgba(1, 1, 1, 1) if self.dark_mode else imgui.get_color_u32_rgba(0.1, 0.1, 0.1, 1)
                
                # Split label by newlines for multi-line text
                lines = label.split('\n')
                for i, line in enumerate(lines):
                    text_width = imgui.calc_text_size(line).x
                    text_x = button_min.x + (button_width - text_width) // 2
                    draw_list.add_text(text_x, text_y + i * 12, text_color, line)
        
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
        
        # Title bar background color (darker than menu bar)
        if self.dark_mode:
            imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, 0.12, 0.12, 0.12, 1.0)
        else:
            imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, 0.85, 0.85, 0.85, 1.0)
        
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
        
        # Title text
        imgui.text(WINDOW_TITLE)
        
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
                    ("point_worldtext", "point_worldtext")
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
                
                imgui.end_menu()
            
            # Settings menu
            window_width = self.get_window_width()
            menu_width = int(window_width * 0.95)  # Keep menu wider but constrain individual items
            imgui.push_style_var(imgui.STYLE_ITEM_INNER_SPACING, (0, 4))  # Minimize spacing between text and checkbox in menu items
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (2, 12))  # Reduce window padding to fit content
            imgui.set_next_window_size(menu_width, 0)
            settings_menu_open = imgui.begin_menu("Settings")
            if imgui.is_item_hovered():
                self.should_show_hand = True
            if settings_menu_open:
                # Constrain menu item width to ensure checkboxes fit
                item_width = min(180, menu_width - 20)
                imgui.set_next_item_width(item_width)
                
                # Dark Mode
                clicked_theme, new_dark_mode = imgui.menu_item("Dark Mode", None, self.dark_mode)
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                if clicked_theme:
                    self.dark_mode = new_dark_mode
                    self.settings.set('appearance_mode', 'dark' if self.dark_mode else 'light')
                    self.setup_style()
                
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
                if imgui.menu_item("Data (open folder)")[0]:
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
                    imgui.text("Remove saved app settings\n(theme, window position, button\nvisibility, etc)")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Clear Version Cache
                if imgui.menu_item("  Clear Version Cache")[0]:
                    self.clear_version_cache()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Remove saved Metamod/CS2KZ\nversion information\n(forces update check)")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Clear Point Worldtext Cache
                if imgui.menu_item("  Clear Point Worldtext Cache")[0]:
                    self.clear_pointworldtext_cache()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Remove temporary character\nimages from Point Worldtext tool")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Clear All Data
                if imgui.menu_item("  Clear All Data")[0]:
                    self.clear_all_data()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Remove all saved data and cache\n(preserves Source2Viewer)")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                # Remove Source2Viewer
                if imgui.menu_item("  Remove Source2Viewer")[0]:
                    self.remove_source2viewer()
                if imgui.is_item_hovered():
                    self.should_show_hand = True
                    imgui.begin_tooltip()
                    imgui.push_text_wrap_pos(250)
                    imgui.text("Remove Source2Viewer executable\nfrom the data folder")
                    imgui.pop_text_wrap_pos()
                    imgui.end_tooltip()
                
                imgui.end_menu()
            imgui.pop_style_var(2)  # Pop both style variables
            
            # Push About to the right side of the menu bar
            # Calculate available space and add spacing
            menu_bar_width = imgui.get_window_width()
            cursor_x = imgui.get_cursor_pos_x()
            about_width = imgui.calc_text_size("About").x + 20  # Add padding
            spacing = menu_bar_width - cursor_x - about_width
            
            if spacing > 0:
                imgui.set_cursor_pos_x(cursor_x + spacing)
            
            # About menu (now on the right)
            about_menu_open = imgui.begin_menu("About")
            if imgui.is_item_hovered():
                self.should_show_hand = True
            if about_menu_open:
                # Credits with clickable names
                draw_list = imgui.get_window_draw_list()
                
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
                
                imgui.end_menu()
            
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
            "point_worldtext": ("point_worldtext", "point_worldtext")
        }
        
        # Render buttons in order, 2 columns or 1 column based on compact mode
        col = 0
        max_cols = 1 if self.compact_mode else 2
        
        for button_name in self.button_order:
            if button_name in button_configs and self.button_visibility.get(button_name, True):
                label, icon = button_configs[button_name]
                
                if col > 0:
                    imgui.same_line(spacing=BUTTON_SPACING)
                
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
                button_width = BUTTON_SIZE
                button_height = BUTTON_SIZE
                icon_size = 56
            
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
                # Normal mode: icon on top, text below
                if self.dragged_button_icon and self.dragged_button_icon in self.button_icons:
                    texture = self.button_icons[self.dragged_button_icon]
                    icon_x = drag_x + (button_width - icon_size) // 2
                    icon_y = drag_y + 15
                    draw_list.add_image(texture, (icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size))
                    text_y = icon_y + icon_size + 8
                else:
                    text_y = drag_y + 45
                
                # Draw label (multi-line)
                lines = self.dragged_button_label.split('\n')
                for i, line in enumerate(lines):
                    text_width = imgui.calc_text_size(line).x
                    text_x = drag_x + (button_width - text_width) // 2
                    draw_list.add_text(text_x, text_y + i * 12, text_color, line)
        
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
            """Extract and run a bundled GUI executable folder (onedir format)"""
            try:
                # If running from source (not frozen), run Python scripts directly
                if not getattr(sys, 'frozen', False):
                    # Map exe names to script paths
                    script_map = {
                        "CS2Importer.exe": "scripts/porting/cs2importer.py",
                        "SkyboxConverter.exe": "scripts/skybox_gui.py",
                        "VTF2PNG.exe": "scripts/vtf2png_gui.py",
                        "LoadingScreenCreator.exe": "scripts/creator_gui.py",
                        "PointWorldText.exe": "scripts/pointworldtext.py"
                    }
                    script_path = script_map.get(exe_name)
                    if script_path:
                        subprocess.Popen([sys.executable, script_path])
                        return
                
                # Get the temp extraction folder
                temp_base = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 
                                         'Temp', '.CS2KZ-mapping-tools')
                os.makedirs(temp_base, exist_ok=True)
                
                # Remove .exe extension to get folder name
                folder_name = exe_name.replace('.exe', '')
                extracted_folder = os.path.join(temp_base, folder_name)
                extracted_exe_path = os.path.join(extracted_folder, exe_name)
                
                # If already extracted, just run it
                if os.path.exists(extracted_exe_path):
                    subprocess.Popen([extracted_exe_path])
                    return
                
                # Extract from bundled resources (onedir structure)
                bundled_folder = resource_path(os.path.join('gui_tools', folder_name))
                
                if os.path.exists(bundled_folder):
                    # Copy entire folder to temp location
                    import shutil
                    shutil.copytree(bundled_folder, extracted_folder, dirs_exist_ok=True)
                    print(f"Extracted {folder_name} to {extracted_folder}")
                    
                    # Run the extracted executable
                    subprocess.Popen([extracted_exe_path])
                else:
                    print(f"Error: {folder_name} not found in bundled resources")
                    
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
    
    def run(self):
        """Main application loop"""
        self.init_window()
        
        # Track time for CS2 detection
        import time
        last_cs2_check = 0
        cs2_check_interval = 2.0  # Check every 2 seconds (reduced overhead)
        
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
        # Destroy custom cursors
        if self.arrow_cursor:
            glfw.destroy_cursor(self.arrow_cursor)
        if self.hand_cursor:
            glfw.destroy_cursor(self.hand_cursor)
        
        self.impl.shutdown()
        glfw.terminate()


if __name__ == "__main__":
    print("CS2KZ Mapping Tools - PyImGui Version")
    print("=" * 50)
    
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
