"""
CS2 Map Importer - PyImGui Interface
Automatically detects CS2 path, modifies required files, and restores them after porting
"""

import imgui
import glfw
from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
import re
import traceback
import sys
import subprocess
import os
import shutil
import tempfile
import winreg
import vdf
from tkinter import filedialog
import tkinter as tk
import webbrowser
import urllib.request
import zipfile
import io

# Constants
CUSTOM_TITLE_BAR_HEIGHT = 30


class CS2ImporterApp:
    def __init__(self):
        self.window = None
        self.impl = None
        
        # Application state
        self.vmf_default_path = "C:\\"
        self.csgo_basefolder = None
        self.vmf_folder = None
        self.vmf_folder_to_save = None
        self.addon = ""
        self.map_name = None
        self.launch_options = "-usebsp"
        
        # UI state
        self.vmf_path_display = "None selected"
        self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)    # Red
        
        # Custom title bar drag state
        self.dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Import completion popup
        self.show_done_popup = False
        
        # Import state tracking
        self.import_in_progress = False
        self.import_completed = False
        
        # Console output
        self.console_output = []
        self.last_console_line_count = 0  # Track for auto-scroll
        
        # Prerequisites visibility (closed by default)
        self.show_guide = False
        self.prerequisites_height = 0  # Track prerequisites section height
        
        # Window dimensions
        self.base_window_height = 300  # Compact base height with room for freeze text
        self.console_height = 640  # Additional height when console is shown
        self.prerequisites_expanded_height = 320  # Reduced height (fewer steps with automation)
        
        # Override print for this instance
        self._original_print = print
        
        # Load saved config
        self.load_from_cfg()
        
        # Auto-detect CS2 path
        self.auto_detect_cs2()
    
    def log(self, message):
        """Add message to console output"""
        self.console_output.append(str(message))
        print(message)  # Also print to actual console
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard using tkinter"""
        try:
            root = tk.Tk()
            root.withdraw()  # Hide the window
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()  # Required to make clipboard persist
            root.destroy()
            self.log("✓ Console output copied to clipboard")
        except Exception as e:
            self.log(f"Error copying to clipboard: {e}")
    
    def init_window(self):
        """Initialize GLFW window and ImGui"""
        if not glfw.init():
            print("Could not initialize OpenGL context")
            sys.exit(1)
        
        # Window hints
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)
        glfw.window_hint(glfw.DECORATED, glfw.FALSE)  # Remove window decorations for custom title bar
        
        # Create window with base height
        self.window = glfw.create_window(360, self.base_window_height, "CS2 Map Importer", None, None)
        if not self.window:
            glfw.terminate()
            print("Could not initialize Window")
            sys.exit(1)
        
        # Center window on screen
        monitor = glfw.get_primary_monitor()
        video_mode = glfw.get_video_mode(monitor)
        window_width = 360
        x_pos = (video_mode.size.width - window_width) // 2
        y_pos = (video_mode.size.height - self.base_window_height) // 2
        glfw.set_window_pos(self.window, x_pos, y_pos)
        
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)  # Enable vsync
        
        # Setup ImGui
        imgui.create_context()
        self.impl = GlfwRenderer(self.window)
        
        # Setup style
        self.setup_style()
    
    def setup_style(self):
        """Configure ImGui visual style to match main.py dark theme"""
        style = imgui.get_style()
        io = imgui.get_io()
        
        io.font_global_scale = 1.0
        
        imgui.style_colors_dark()
        # Match CustomTkinter dark theme
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = (0.1, 0.1, 0.1, 1.0)
        style.colors[imgui.COLOR_MENUBAR_BACKGROUND] = (0.16, 0.16, 0.16, 1.0)
        style.colors[imgui.COLOR_BUTTON] = (0.29, 0.29, 0.29, 1.0)
        style.colors[imgui.COLOR_BUTTON_HOVERED] = (0.35, 0.35, 0.35, 1.0)
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = (0.40, 0.40, 0.40, 1.0)
        style.colors[imgui.COLOR_BORDER] = (0.40, 0.40, 0.40, 1.0)
        style.colors[imgui.COLOR_TEXT] = (1.0, 1.0, 1.0, 1.0)
        style.colors[imgui.COLOR_FRAME_BACKGROUND] = (0.16, 0.16, 0.16, 1.0)
        style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = (0.20, 0.20, 0.20, 1.0)
        style.colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = (0.25, 0.25, 0.25, 1.0)
        style.colors[imgui.COLOR_CHECK_MARK] = (1.0, 0.6, 0.0, 1.0)  # Orange accent
        
        # Window rounding
        style.window_rounding = 0.0
        style.frame_rounding = 3.0
        style.grab_rounding = 3.0
        style.window_border_size = 1.0
        style.frame_border_size = 0.0
        style.window_padding = (10, 10)
        style.frame_padding = (8, 4)
        style.item_spacing = (8, 8)
    
    def get_steam_directory(self):
        """Get Steam installation directory from registry"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                return steam_path
        except FileNotFoundError:
            return None

    def find_cs2_library_path(self, libraryfolders_path):
        """Find CS2 library path from Steam library folders"""
        if not os.path.exists(libraryfolders_path):
            return None

        with open(libraryfolders_path, 'r', encoding='utf-8') as file:
            library_data = vdf.load(file)

        if 'libraryfolders' in library_data:
            for _, folder in library_data['libraryfolders'].items():
                if 'apps' in folder and '730' in folder['apps']:
                    return folder['path']
        return None

    def get_cs2_path(self):
        """Get CS2 installation path"""
        steam_path = self.get_steam_directory()
        if steam_path is None:
            return None
        library_path = self.find_cs2_library_path(os.path.join(steam_path, "steamapps", "libraryfolders.vdf"))
        if library_path is None:
            return None
        with open(os.path.join(library_path, 'steamapps', 'appmanifest_730.acf'), 'r', encoding='utf-8') as file:
            installdir = vdf.load(file)['AppState']['installdir']
            return os.path.join(library_path, 'steamapps', 'common', installdir)

    def auto_detect_cs2(self):
        """Automatically detect and set CS2 path"""
        try:
            cs2_path = self.get_cs2_path()
            if cs2_path:
                self.csgo_basefolder = cs2_path
                print(f"CS2 detected at: {cs2_path}")
        except Exception as e:
            print(f"Could not auto-detect CS2: {e}")

    def select_vmf(self):
        """Open file dialog to select BSP file and auto-extract"""
        # Make sure the main window doesn't block
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)  # Keep dialog on top
        root.update()  # Process events
        
        path = filedialog.askopenfilename(
            title="Select a BSP file to import",
            initialdir=self.vmf_default_path,
            filetypes=[("BSP files", "*.bsp"), ("All files", "*.*")],
            parent=root
        )
        root.destroy()
        
        if not path:
            return
        
        path = path.replace("\\", "/")
        bsp_filename = os.path.basename(path)
        self.map_name = os.path.splitext(bsp_filename)[0]
        
        # Auto-extract BSP using BSPSource
        if not self.extract_bsp(path):
            self.log("Failed to extract BSP file")
            self.vmf_path_display = "Extraction failed"
            self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)
            return
        
        # Set VMF path to the extracted location in csgo folder
        # BSPSource creates VMF with same name as BSP (no suffix)
        if self.csgo_basefolder:
            csgo_maps_folder = os.path.join(self.csgo_basefolder.replace("/", "\\"), "csgo", "maps")
            vmf_path = os.path.join(csgo_maps_folder, f"{self.map_name}.vmf")
            
            if os.path.exists(vmf_path):
                self.vmf_folder = csgo_maps_folder.replace("\\", "/")
                self.vmf_path_display = f"{self.map_name}.vmf (extracted)"
                self.vmf_status_color = (0.0, 1.0, 0.0, 1.0)
                self.vmf_default_path = os.path.dirname(path)
            else:
                self.log(f"VMF not found at: {vmf_path}")
                self.vmf_path_display = "VMF not found after extraction"
                self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)
        else:
            self.log("CS:GO folder not detected")
            self.vmf_path_display = "CS:GO folder not found"
            self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)
    
    def fix_vmf_structure(self, vmf_path):
        """Add proper VMF header structure for CS2 importer compatibility"""
        try:
            # Read the VMF file
            with open(vmf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check if it already has versioninfo (Hammer-formatted VMF)
            if 'versioninfo' in content.lower():
                self.log("VMF already has proper structure")
                return
            
            # Add proper VMF header
            vmf_header = '''versioninfo
{
\t"editorversion" "400"
\t"editorbuild" "8997"
\t"mapversion" "1"
\t"formatversion" "100"
\t"prefab" "0"
}
visgroups
{
}
viewsettings
{
\t"bSnapToGrid" "1"
\t"bShowGrid" "1"
\t"bShowLogicalGrid" "0"
\t"nGridSpacing" "64"
}
'''
            # Prepend header to existing content
            new_content = vmf_header + content
            
            # Write back
            with open(vmf_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.log("✓ Fixed VMF structure for CS2 compatibility")
            
        except Exception as e:
            self.log(f"Warning: Could not fix VMF structure: {e}")
    
    def extract_bsp(self, bsp_path):
        """Extract BSP file using BSPSource"""
        try:
            if not self.csgo_basefolder:
                self.log("CS:GO folder not set")
                return False
            
            # Check/download BSPSource to temp folder
            temp_dir = tempfile.gettempdir()
            bspsrc_dir = os.path.join(temp_dir, "bspsrc")
            bspsrc_bat = os.path.join(bspsrc_dir, "bspsrc.bat")
            
            if not os.path.exists(bspsrc_bat):
                self.log("Downloading BSPSource...")
                try:
                    # Download latest BSPSource Windows release
                    bspsrc_url = "https://github.com/ata4/bspsrc/releases/download/v1.4.7/bspsrc-windows.zip"
                    
                    # Download zip to memory
                    response = urllib.request.urlopen(bspsrc_url)
                    zip_data = io.BytesIO(response.read())
                    
                    # Extract zip to temp folder
                    os.makedirs(bspsrc_dir, exist_ok=True)
                    with zipfile.ZipFile(zip_data) as zip_ref:
                        zip_ref.extractall(bspsrc_dir)
                    
                    self.log("BSPSource downloaded and extracted successfully")
                except Exception as e:
                    self.log(f"Failed to download BSPSource: {e}")
                    return False
            

            # Create a unique temporary directory for BSPSource output
            # Using mkdtemp ensures a unique, safe directory that doesn't conflict
            temp_output_dir = tempfile.mkdtemp(prefix="bspsrc_output_")
            
            # BSPSource needs the FULL VMF OUTPUT PATH, not just directory
            map_base_name = os.path.splitext(os.path.basename(bsp_path))[0]
            temp_vmf = os.path.join(temp_output_dir, f"{map_base_name}.vmf")
            
            self.log(f"Using temp directory: {temp_output_dir}")
            self.log(f"Target VMF: {temp_vmf}")

            # Ensure csgo directory exists
            base_dir = self.csgo_basefolder.replace("/", "\\")
            csgo_dir = os.path.join(base_dir, "csgo")
            os.makedirs(csgo_dir, exist_ok=True)


            self.log(f"Extracting {os.path.basename(bsp_path)}...")
            
            # Call Java directly instead of batch file for better control
            java_exe = os.path.join(bspsrc_dir, "bin", "java.exe")
            
            # Normalize paths for Windows - ensure backslashes
            temp_vmf_normalized = temp_vmf.replace("/", "\\")
            bsp_path_normalized = bsp_path.replace("/", "\\")
            
            command = [
                java_exe,
                "-m", "info.ata4.bspsrc.app/info.ata4.bspsrc.app.src.cli.BspSourceCli",
                "--unpack_embedded",  # Extract embedded files (materials, models, sounds, etc.)
                "-o", temp_vmf_normalized,
                bsp_path_normalized
            ]
            self.log(f"Running command: {' '.join(command)}")
            self.log(f"Working directory: {bspsrc_dir}")
            # Use Popen to capture output
            process = subprocess.Popen(
                command,
                cwd=bspsrc_dir,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Read output line by line
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log(line)
            
            process.wait(timeout=120)
            
            self.log(f"Process finished with return code: {process.returncode}")

            # Check what BSPSource actually extracted
            self.log(f"Checking temp directory contents: {temp_output_dir}")
            if os.path.exists(temp_output_dir):
                for item in os.listdir(temp_output_dir):
                    item_path = os.path.join(temp_output_dir, item)
                    if os.path.isdir(item_path):
                        self.log(f"  Found folder: {item}/")
                        # Show contents of folders
                        for subitem in os.listdir(item_path):
                            self.log(f"    - {subitem}")
                    else:
                        self.log(f"  Found file: {item}")

            # Check for output files regardless of return code (BSPSource may return non-zero but still extract)
            if True:  # Always check for extracted files
                # BSPSource extracts files to temp_output_dir/mapname/ folder
                map_base_name = os.path.splitext(os.path.basename(bsp_path))[0]
                extracted_folder = os.path.join(temp_output_dir, map_base_name)
                
                # Check if files were extracted to mapname subfolder (BSPSource behavior)
                if os.path.exists(extracted_folder):
                    temp_maps = os.path.join(extracted_folder, "maps")
                    temp_materials = os.path.join(extracted_folder, "materials")
                else:
                    # Fallback to root temp directory
                    temp_maps = os.path.join(temp_output_dir, "maps")
                    temp_materials = os.path.join(temp_output_dir, "materials")
                
                csgo_maps = os.path.join(csgo_dir, "maps")
                csgo_materials = os.path.join(csgo_dir, "materials")
                
                # VMF file path (already defined above)
                csgo_vmf = os.path.join(csgo_maps, os.path.basename(temp_vmf))  # Move it to maps folder for the importer
                
                # Move VMF file
                if os.path.exists(temp_vmf):
                    os.makedirs(csgo_maps, exist_ok=True)
                    shutil.copy2(temp_vmf, csgo_vmf)
                    self.log(f"Copied {os.path.basename(temp_vmf)} to csgo/maps/")
                    
                    # Fix VMF structure for CS2 importer compatibility
                    self.fix_vmf_structure(csgo_vmf)
                
                # Move maps folder contents (nav files)
                if os.path.exists(temp_maps):
                    os.makedirs(csgo_maps, exist_ok=True)
                    for item in os.listdir(temp_maps):
                        src = os.path.join(temp_maps, item)
                        dst = os.path.join(csgo_maps, item)
                        if os.path.isfile(src):
                            shutil.copy2(src, dst)
                            self.log(f"Copied {item} to csgo/maps/")
                
                # Move models folder contents (embedded custom models)
                temp_models = os.path.join(extracted_folder, "models") if os.path.exists(extracted_folder) else os.path.join(temp_output_dir, "models")
                if os.path.exists(temp_models):
                    self.log("Extracting embedded models...")
                    csgo_models = os.path.join(csgo_dir, "models")
                    os.makedirs(csgo_models, exist_ok=True)
                    
                    # Also create models folder in content directory (maps/)
                    csgo_maps_models = os.path.join(csgo_maps, "models")
                    os.makedirs(csgo_maps_models, exist_ok=True)
                    
                    model_count = 0
                    for root, dirs, files in os.walk(temp_models):
                        rel_path = os.path.relpath(root, temp_models)
                        dst_dir_game = os.path.join(csgo_models, rel_path) if rel_path != "." else csgo_models
                        dst_dir_content = os.path.join(csgo_maps_models, rel_path) if rel_path != "." else csgo_maps_models
                        os.makedirs(dst_dir_game, exist_ok=True)
                        os.makedirs(dst_dir_content, exist_ok=True)
                        for file in files:
                            src = os.path.join(root, file)
                            # Copy to both game and content directories
                            dst_game = os.path.join(dst_dir_game, file)
                            dst_content = os.path.join(dst_dir_content, file)
                            shutil.copy2(src, dst_game)
                            shutil.copy2(src, dst_content)
                            model_count += 1
                            # Log relative path to show model structure
                            rel_file = os.path.join(rel_path, file) if rel_path != "." else file
                            self.log(f"  Copied model: {rel_file}")
                    
                    self.log(f"✓ Extracted {model_count} model files")
                else:
                    self.log("⚠ No embedded models found in BSP")
                
                # Move materials folder contents  
                # Copy to BOTH game dir (csgo/materials/) AND content dir (csgo/maps/materials/)
                # for source1import to find them
                if os.path.exists(temp_materials):
                    self.log("Extracting embedded materials...")
                    os.makedirs(csgo_materials, exist_ok=True)
                    
                    # Also create materials folder in content directory (maps/)
                    csgo_maps_materials = os.path.join(csgo_maps, "materials")
                    os.makedirs(csgo_maps_materials, exist_ok=True)
                    
                    material_count = 0
                    extracted_vmts = []  # Track VMT files for refs list
                    for root, dirs, files in os.walk(temp_materials):
                        rel_path = os.path.relpath(root, temp_materials)
                        dst_dir_game = os.path.join(csgo_materials, rel_path) if rel_path != "." else csgo_materials
                        dst_dir_content = os.path.join(csgo_maps_materials, rel_path) if rel_path != "." else csgo_maps_materials
                        os.makedirs(dst_dir_game, exist_ok=True)
                        os.makedirs(dst_dir_content, exist_ok=True)
                        for file in files:
                            src = os.path.join(root, file)
                            # Copy to both game and content directories
                            dst_game = os.path.join(dst_dir_game, file)
                            dst_content = os.path.join(dst_dir_content, file)
                            shutil.copy2(src, dst_game)
                            shutil.copy2(src, dst_content)
                            material_count += 1
                            # Log relative path to show material structure
                            rel_file = os.path.join(rel_path, file) if rel_path != "." else file
                            self.log(f"  Copied material: {rel_file}")
                            
                            # Track VMT files for creating refs list
                            if file.lower().endswith('.vmt'):
                                # Convert to material path (remove .vmt and use forward slashes)
                                mat_path = rel_file.replace('\\', '/').rsplit('.', 1)[0]
                                extracted_vmts.append(mat_path)
                    
                    self.log(f"✓ Extracted {material_count} material files")
                    
                    # Create _refs.txt file for the importer to process embedded materials
                    # Format must match source1import's expected KeyValues format
                    if extracted_vmts:
                        refs_file = os.path.join(csgo_maps, f"{map_base_name}_embedded_refs.txt")
                        with open(refs_file, 'w') as f:
                            f.write('importfilelist\n{\n')
                            for vmt in extracted_vmts:
                                # Use forward slashes and proper quoting like the example files
                                mat_path = vmt.replace('\\', '/')
                                f.write(f'\t"file" "materials/{mat_path}.vmt"\n')
                            f.write('}\n')
                        self.log(f"✓ Created refs file with {len(extracted_vmts)} embedded materials")
                else:
                    self.log("⚠ No embedded materials found in BSP")
                
                # Clean up temp folder
                try:
                    if os.path.exists(temp_output_dir):
                        shutil.rmtree(temp_output_dir)
                except Exception as e:
                    self.log(f"Warning: Could not clean up temp directory: {e}")
                
                # Check if VMF was successfully moved
                if os.path.exists(csgo_vmf):
                    self.log(f"✓ VMF found at: {csgo_vmf}")
                    self.log("✓ Extraction completed successfully")
                    return True
                else:
                    # Check if embedded files were at least extracted
                    if os.path.exists(csgo_materials) and os.listdir(csgo_materials):
                        self.log("⚠ Embedded files extracted, but VMF decompilation failed")
                        self.log("⚠ This BSP may be protected or corrupted")
                        self.log("⚠ Try downloading a different version of this map from:")
                        self.log("   https://files.femboy.kz/fastdl/csgo/maps/")
                    else:
                        self.log("✗ VMF not found. BSP may be corrupt or CS2 format.")
                        self.log("✗ Note: This tool only works with CS:GO/Source 1 BSP files.")
                    return False
                
        except subprocess.TimeoutExpired:
            self.log("Extraction timed out (took more than 2 minutes)")
            return False
        except Exception as e:
            self.log(f"Error during extraction: {e}")
            return False
        
        # Save the folder path for next time
        self.vmf_default_path = self.vmf_folder

        # if path doesn't end with /maps
        if not self.vmf_folder.endswith("/maps"):
            temp_dir = tempfile.gettempdir()

            # check if /maps is in temp already, otherwise create it
            if not os.path.exists(temp_dir + "/maps"):
                os.mkdir(temp_dir + "/maps")
            
            # delete vmf in /maps if exists, as maybe it isn't the newest ver. 
            else:
                if os.path.isfile(temp_dir + "/maps/" + self.map_name + ".vmf"):
                    os.remove(temp_dir + "/maps/" + self.map_name + ".vmf")

            # copy *.vmf to temp/maps/*.vmf
            shutil.copy(self.vmf_folder + "/" + self.map_name + ".vmf", temp_dir + "/maps")
            
            self.vmf_folder_to_save = self.vmf_folder
            self.vmf_folder = temp_dir

        else:
            self.vmf_folder = "/".join(self.vmf_folder.split("/")[:-1])
            self.vmf_folder_to_save = self.vmf_folder

        # update UI
        self.vmf_path_display = path
        self.vmf_status_color = (0.0, 1.0, 0.0, 1.0)  # Green

    def save_to_cfg(self):
        """Save configuration to file"""
        config_path = os.path.join(os.path.dirname(__file__), "cs2importer.cfg")
        default_path = self.vmf_default_path if self.vmf_default_path else 'C:\\'
        temp = f"""{self.launch_options}
{self.csgo_basefolder if self.csgo_basefolder else ''}
{default_path}"""
        
        with open(config_path, "w") as f:
            f.write(temp)

    def load_from_cfg(self):
        """Load configuration from file"""
        config_path = os.path.join(os.path.dirname(__file__), "cs2importer.cfg")
        
        if not os.path.isfile(config_path):
            return

        try:
            with open(config_path, "r") as f:
                temp = f.readlines()
                if not temp:
                    return

            if len(temp) > 0:
                self.launch_options = temp[0].strip()
            if len(temp) > 1 and temp[1].strip():
                self.set_csgo_folder(temp[1].strip())
            if len(temp) > 2 and temp[2].strip():
                self.vmf_default_path = temp[2].strip()
        except:
            pass

    def go(self):
        """Execute the import process"""
        try:
            if not self.csgo_basefolder:
                self.log("Error: CS:GO folder not detected")
                return
            
            if not self.vmf_folder or not self.map_name:
                self.log("Error: VMF file not selected")
                return
            
            if not self.addon:
                self.log("Error: Addon name not specified")
                return
            
            # Set import state
            self.import_in_progress = True
            self.import_completed = False
            self.console_output = []  # Clear previous output
            
            self.save_to_cfg()

            cd = os.path.join(self.csgo_basefolder, 'game', 'csgo', 'import_scripts').replace("/", "\\")
            
            # Get the path to our custom import script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            jakke_script = os.path.join(script_dir, 'import_map_community_jakke.py').replace("/", "\\")
            
            # Build command using our custom script
            command = f'python "{jakke_script}" '
            command += '"' + os.path.join(self.csgo_basefolder, 'csgo').replace("/", "\\") + '" '
            command += '"' + self.vmf_folder.replace("/", "\\") + '" '
            command += '"' + os.path.join(self.csgo_basefolder, 'game', 'csgo').replace("/", "\\") + '" '
            command += self.addon + ' '
            command += self.map_name + ' '
            command += self.launch_options
            
            self.log("Starting import process...")
            
            # Run the process without stdin/stdout pipes - let it run directly
            # Use unbuffered Python output
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            process = subprocess.Popen(
                command, 
                cwd=cd, 
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=0,  # Unbuffered
                env=env
            )
            
            # Read output line by line in real-time
            import threading
            def read_output():
                try:
                    while True:
                        line = process.stdout.readline()
                        if not line:
                            break
                        line = line.rstrip()
                        if line:
                            self.log(line)
                except Exception as e:
                    self.log(f"Output read error: {e}")
            
            output_thread = threading.Thread(target=read_output, daemon=True)
            output_thread.start()
            
            # Wait for process to complete
            process.wait()
            output_thread.join(timeout=2)  # Wait up to 2 seconds for output thread
            self.log("Import process completed.")
            
            # Update import state
            self.import_in_progress = False
            self.import_completed = True
            
            # Show done popup
            self.show_done_popup = True

        except Exception as e:
            self.log(f"Error: {e}")
            # Update import state on error
            self.import_in_progress = False
            self.import_completed = True
            # Restore files even if there's an error
            try:
                self.restore_files()
            except:
                pass

    def render_custom_title_bar(self):
        """Render custom title bar with minimize and close buttons"""
        window_width, _ = glfw.get_window_size(self.window)
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(window_width, CUSTOM_TITLE_BAR_HEIGHT)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        
        # Title bar background color (darker gray)
        imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, 0.12, 0.12, 0.12, 1.0)
        
        flags = (
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_SCROLLBAR
        )
        
        imgui.begin("##titlebar", flags=flags)
        
        # Title text
        imgui.text("CS2 Map Importer")
        
        # Get the position for the buttons (right side)
        button_size = 20
        button_spacing = 4
        total_button_width = (button_size * 2) + button_spacing
        
        imgui.same_line(window_width - total_button_width - 6)
        
        # VS Code style buttons
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 0.0)
        
        # Minimize button
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.2, 0.2, 0.2, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)
        
        minimize_clicked = imgui.button("##minimize", width=button_size, height=button_size)
        
        # Draw minimize symbol
        min_button_min = imgui.get_item_rect_min()
        draw_list = imgui.get_window_draw_list()
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
        
        # Close button (red hover)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.9, 0.2, 0.2, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.8, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)
        
        close_clicked = imgui.button("##close", width=button_size, height=button_size)
        
        # Draw X symbol
        close_button_min = imgui.get_item_rect_min()
        center_x = close_button_min.x + button_size // 2
        center_y = close_button_min.y + button_size // 2
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
        
        imgui.pop_style_var(1)
        
        # Handle window dragging from title bar
        if imgui.is_window_hovered() and imgui.is_mouse_clicked(0):
            mouse_pos = imgui.get_mouse_pos()
            if mouse_pos.x < window_width - total_button_width - 15:
                window_pos = glfw.get_window_pos(self.window)
                self.dragging_window = True
                # Store the offset from window position to cursor
                cursor_pos = glfw.get_cursor_pos(self.window)
                self.drag_offset_x = cursor_pos[0]
                self.drag_offset_y = cursor_pos[1]
        
        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(3)

    def render(self):
        """Render the ImGui interface"""
        # Render custom title bar first
        self.render_custom_title_bar()
        
        window_width, window_height = glfw.get_window_size(self.window)
        imgui.set_next_window_position(0, CUSTOM_TITLE_BAR_HEIGHT)
        imgui.set_next_window_size(window_width, window_height - CUSTOM_TITLE_BAR_HEIGHT)
        
        imgui.begin(
            "CS2 Map Importer",
            flags=imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_MOVE | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )
        
        # Content (remove duplicate title since it's in title bar now)
        imgui.spacing()
        
        # Prerequisites Section
        prerequisites_opened = imgui.collapsing_header("Prerequisites (Read Before Import!)")[0]
        
        # Dynamically resize window based on prerequisites and console state
        current_height = self.base_window_height
        current_width = 360  # Base width - 20% narrower (was 450)
        if prerequisites_opened:
            current_height += self.prerequisites_expanded_height
            current_width = 520  # Slightly wider for prerequisites text
        if self.import_completed:
            current_height += self.console_height
            current_width = 600  # Wider for console
        
        current_window_size = glfw.get_window_size(self.window)
        
        if current_window_size[0] != current_width or current_window_size[1] != current_height:
            glfw.set_window_size(self.window, current_width, current_height)
        
        if prerequisites_opened:
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.8, 0.2, 1.0)  # Yellow text
            imgui.text_wrapped("Follow these steps BEFORE using the importer:")
            imgui.pop_style_color()
            
            imgui.spacing()
            imgui.push_text_wrap_pos(imgui.get_content_region_available_width())
            
            # Step 1 - White
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 1.0, 1.0)  # White
            imgui.bullet_text("1. Download a CS:GO (Source 1) BSP file from FKZ database:")
            imgui.indent()
            
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.6, 0.6, 1.0)  # Light red for warning
            imgui.text_wrapped("IMPORTANT: Must be CS:GO format, NOT CS2!")
            imgui.pop_style_color()
            imgui.pop_style_color()
            
            imgui.spacing()
            
            # FKZ link - clickable and copyable
            fkz_url = "https://files.femboy.kz/fastdl/csgo/maps/"
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.8, 1.0, 1.0)
            if imgui.selectable(fkz_url, False)[0]:
                webbrowser.open(fkz_url)
            imgui.pop_style_color()
            
            # Show hand cursor on hover
            if imgui.is_item_hovered():
                imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)
            
            imgui.unindent()
            
            # Step 2 - Grey
            imgui.push_style_color(imgui.COLOR_TEXT, 0.7, 0.7, 0.7, 1.0)  # Light grey
            imgui.bullet_text("2. Add CS2 win64 folder to PATH:")
            imgui.text_wrapped("Required: CS2\\game\\bin\\win64\\ folder must be in PATH")
            imgui.pop_style_color()
            imgui.indent()
            imgui.spacing()
            
            # Buttons for PATH setup
            if imgui.button("Open win64 Folder", width=140):
                if self.csgo_basefolder:
                    win64_path = os.path.join(self.csgo_basefolder, 'game', 'bin', 'win64')
                    if os.path.exists(win64_path):
                        subprocess.Popen(f'explorer "{win64_path}"')
                    else:
                        self.log("Error: win64 folder not found")
                else:
                    self.log("Error: CS2 path not detected")
            
            imgui.same_line()
            
            if imgui.button("Open PATH Settings", width=140):
                # Open Windows Environment Variables dialog
                subprocess.Popen('rundll32.exe sysdm.cpl,EditEnvironmentVariables')
            
            imgui.spacing()
            imgui.push_style_color(imgui.COLOR_TEXT, 0.7, 0.7, 0.7, 1.0)  # Light grey
            imgui.text_wrapped('In "User variables" window -> click "Path" -> "Edit..." -> "New"')
            imgui.text_wrapped('-> Copy-paste the whole win64 path -> click "OK"')
            imgui.pop_style_color()
            
            imgui.unindent()
            
            # Step 3 - White
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 1.0, 1.0)  # White
            imgui.bullet_text("3. Now select a BSP file below to auto-extract and import")
            imgui.pop_style_color()
            
            imgui.spacing()
            
            # Note about automated process
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.8, 0.2, 1.0)  # Yellow
            imgui.text_wrapped("The importer will automatically extract the BSP with all assets")
            imgui.pop_style_color()
            
            imgui.pop_text_wrap_pos()
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
        
        # BSP File Selection
        imgui.text("BSP File:")
        if imgui.button("Select BSP File", width=200):
            self.select_vmf()
        
        # Display VMF path below button with smaller text
        imgui.push_style_color(imgui.COLOR_TEXT, *self.vmf_status_color)
        imgui.set_window_font_scale(0.85)  # Make text smaller
        imgui.text_wrapped(self.vmf_path_display)
        imgui.set_window_font_scale(1.0)  # Reset font scale
        imgui.pop_style_color()
        
        imgui.spacing()
        imgui.spacing()
        
        # Addon Name Input
        imgui.text("Addon Name:")
        imgui.set_next_item_width(200)
        _, self.addon = imgui.input_text("##addon", self.addon, 256)
        
        imgui.spacing()
        imgui.separator()
        
        # Add extra padding before GO button if prerequisites are open
        if prerequisites_opened:
            imgui.spacing()
            imgui.spacing()
        
        # GO Button
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.7, 0.2, 1.0)  # Green
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.8, 0.3, 1.0)  # Lighter green
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.6, 0.15, 1.0)  # Darker green
        
        # Disable button while import is in progress
        if self.import_in_progress:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        
        button_clicked = imgui.button("GO!", width=100, height=40)
        
        if self.import_in_progress:
            imgui.pop_style_var(1)
        
        if button_clicked and not self.import_in_progress:
            self.go()
        
        imgui.pop_style_color(3)
        
        # Copy All button (only show after import is completed)
        if self.import_completed:
            imgui.same_line()
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.5, 0.8, 1.0)  # Blue
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.6, 0.9, 1.0)  # Lighter blue
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.4, 0.7, 1.0)  # Darker blue
            
            if imgui.button("Copy All", width=100, height=40):
                # Copy console output to clipboard
                console_text = "\n".join(self.console_output)
                self.copy_to_clipboard(console_text)
            
            imgui.pop_style_color(3)
        
        # Note about window freezing
        if not self.import_in_progress and not self.import_completed:
            imgui.push_style_color(imgui.COLOR_TEXT, 0.7, 0.7, 0.7, 1.0)  # Grey
            imgui.text("(Window will freeze during import)")
            imgui.pop_style_color()
        
        # Show "wait..." text during import
        if self.import_in_progress:
            imgui.same_line()
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.8, 0.2, 1.0)  # Yellow
            imgui.text("wait...")
            imgui.pop_style_color()
        
        # Only show console output section after import is completed
        if self.import_completed:
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
            
            # Console Output
            imgui.text("Console Output:")
            
            # Check if new content was added
            current_line_count = len(self.console_output)
            should_scroll = current_line_count > self.last_console_line_count
            self.last_console_line_count = current_line_count
            
            # Use a child window with scrollbars for console output
            imgui.push_style_color(imgui.COLOR_CHILD_BACKGROUND, 0.1, 0.1, 0.1, 1.0)
            imgui.begin_child("console_region", 0, 600, True, imgui.WINDOW_HORIZONTAL_SCROLLING_BAR)
            
            # Render each line as selectable text (allows copy with ctrl+c)
            for line in self.console_output:
                imgui.selectable(line, False)
            
            # Auto-scroll to bottom when new content is added
            if should_scroll:
                imgui.set_scroll_here_y(1.0)  # 1.0 = bottom
            
            imgui.end_child()
            imgui.pop_style_color()
        
        imgui.end()
        
        # Done popup
        if self.show_done_popup:
            imgui.open_popup("Import Complete")
        
        if imgui.begin_popup_modal("Import Complete", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
            imgui.text("Map import completed successfully!")
            imgui.spacing()
            imgui.spacing()
            
            if imgui.button("OK", width=120):
                self.show_done_popup = False
                imgui.close_current_popup()
            
            imgui.end_popup()

    def run(self):
        """Main application loop"""
        self.init_window()
        
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.impl.process_inputs()
            
            # Handle window dragging
            if self.dragging_window:
                if imgui.is_mouse_down(0):
                    # Get cursor position in screen coordinates
                    cursor_pos = glfw.get_cursor_pos(self.window)
                    window_pos = glfw.get_window_pos(self.window)
                    
                    # Calculate new window position
                    new_x = int(window_pos[0] + cursor_pos[0] - self.drag_offset_x)
                    new_y = int(window_pos[1] + cursor_pos[1] - self.drag_offset_y)
                    glfw.set_window_pos(self.window, new_x, new_y)
                else:
                    self.dragging_window = False
            
            imgui.new_frame()
            
            self.render()
            
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            
            imgui.render()
            self.impl.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)
        
        self.impl.shutdown()
        glfw.terminate()


if __name__ == "__main__":
    app = CS2ImporterApp()
    app.run()
