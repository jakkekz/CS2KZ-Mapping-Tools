import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
import os
import sys
import json
import subprocess
from settings_manager import SettingsManager

# Initial CustomTkinter setup
ctk.set_default_color_theme("blue")

class RoundedButton(ctk.CTkButton):
    def __init__(self, parent, text, command, image_path=None, settings_command=None, grid_column=0, button_name=None, app=None, **kwargs):
        # Create a frame to hold the button with padding
        self.frame = ctk.CTkFrame(parent, width=126, height=126, fg_color="transparent")  # 180 * 0.7 = 126
        self.frame.pack_propagate(False)
        self.frame.grid_propagate(False)
        
        # Store button name and app reference for drag-and-drop
        self.button_name = button_name
        self.app = app
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Initialize the button first
        super().__init__(
            self.frame,
            text=text,
            command=command,  # Use original command directly
            width=112,  # 160 * 0.7 = 112
            height=112,  # 160 * 0.7 = 112
            corner_radius=7,  # 10 * 0.7 = 7
            font=("Segoe UI", 9, "bold"),  # 13 * 0.7 ≈ 9
            fg_color=("gray75", "gray25"),
            hover_color=("gray70", "gray30"),
            text_color=("gray10", "white"),
            border_width=2,
            border_color=("gray60", "gray40"),
            **kwargs
        )
        
        # Load and set image after button is initialized
        if image_path and os.path.exists(image_path):
            try:
                from PIL import Image
                pil_image = Image.open(image_path)
                image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(56, 56))  # 80 * 0.7 = 56
                self.configure(image=image, compound="top")
            except Exception:
                self.configure(compound="center")
        else:
            self.configure(compound="center")
        
        # Configure frame grid for centering
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=1)
        
        # Place button in the frame with equal padding
        self.grid_configure(row=0, column=0, padx=7, pady=7, sticky="nsew")  # Equal padding on all sides

        # Create move handle at the top-left of the button (conditional on settings)
        if app and button_name:
            # Get the button background color
            is_dark = ctk.get_appearance_mode() == "Dark"
            button_bg = self._apply_appearance_mode(self.cget("fg_color"))
            
            # Create a label for the move icon
            self.move_handle = tk.Label(
                self,  # Parent is the main button
                text="✥",  # Move/drag icon (circled plus/crosshair)
                font=("Segoe UI", 14),  # 20 * 0.7 = 14
                bg=button_bg,  # Match button background
                fg="gray60" if is_dark else "gray40",
                cursor="fleur",  # Move cursor (four arrows)
                bd=0,  # No border
                highlightthickness=0  # No highlight
            )
            
            # Position move handle at the top-left corner of the button
            self.move_handle.place(relx=0.05, rely=0.05, anchor="nw")
            
            # Check settings to show/hide move icon
            show_move_icons = app.settings.get('show_move_icons', False)
            if not show_move_icons:
                self.move_handle.place_forget()
            
            # Bind hover effects
            self.move_handle.bind("<Enter>", lambda e: self.move_handle.config(fg="white" if is_dark else "black"))
            self.move_handle.bind("<Leave>", lambda e: self.move_handle.config(fg="gray60" if is_dark else "gray40"))
            
            # Bind drag events to the move handle ONLY
            self.move_handle.bind("<Button-1>", self.on_drag_start)
            self.move_handle.bind("<B1-Motion>", self.on_drag_motion)
            self.move_handle.bind("<ButtonRelease-1>", self.on_drag_end)

        # Create and configure settings button at the top-right of the button
        if settings_command:
            # Get the button background color
            is_dark = ctk.get_appearance_mode() == "Dark"
            button_bg = self._apply_appearance_mode(self.cget("fg_color"))
            
            # Create a transparent label for the cogwheel on the button itself
            self.settings_button = tk.Label(
                self,  # Parent is the main button
                text="⚙",  # Gear emoji as settings icon
                font=("Segoe UI", 10),  # 14 * 0.7 = 10
                bg=button_bg,  # Match button background
                fg="gray60" if is_dark else "gray40",
                cursor="hand2",  # Hand cursor to indicate clickability
                bd=0,  # No border
                highlightthickness=0  # No highlight
            )
            
            # Position settings button at the top-right corner of the button
            self.settings_button.place(relx=0.95, rely=0.05, anchor="ne")
            
            # Bind click event and hover effects
            self.settings_button.bind("<Button-1>", lambda e: settings_command())
            self.settings_button.bind("<Enter>", lambda e: self.settings_button.config(fg="white" if is_dark else "black"))
            self.settings_button.bind("<Leave>", lambda e: self.settings_button.config(fg="gray60" if is_dark else "gray40"))
    
    def on_drag_start(self, event):
        """Start dragging the button from the move handle"""
        self.is_dragging = True
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        # Store initial grid info before lifting
        grid_info = self.frame.grid_info()
        self.initial_row = grid_info.get('row')
        self.initial_col = grid_info.get('column')
        # Raise the frame to top layer
        self.frame.lift()
        # Change appearance to indicate dragging
        self.configure(border_color="blue")
    
    def on_drag_motion(self, event):
        """Handle drag motion"""
        if self.is_dragging:
            # Calculate new position relative to the move handle
            x = self.frame.winfo_x() + event.x - self.drag_start_x
            y = self.frame.winfo_y() + event.y - self.drag_start_y
            # Move the frame
            self.frame.place(x=x, y=y)
    
    def on_drag_end(self, event):
        """End dragging and swap button positions"""
        if self.is_dragging:
            self.is_dragging = False
            # Reset border color
            is_dark = ctk.get_appearance_mode() == "Dark"
            self.configure(border_color=("gray60", "gray40"))
            
            # IMPORTANT: Remove place geometry before restoring grid
            self.frame.place_forget()
            
            # Find which button we're hovering over
            x = self.frame.winfo_rootx() + event.x
            y = self.frame.winfo_rooty() + event.y
            
            target_button = None
            for btn in self.app.all_buttons:
                if btn != self and btn.frame.winfo_ismapped():
                    btn_x = btn.frame.winfo_rootx()
                    btn_y = btn.frame.winfo_rooty()
                    btn_width = btn.frame.winfo_width()
                    btn_height = btn.frame.winfo_height()
                    
                    if (btn_x <= x <= btn_x + btn_width and 
                        btn_y <= y <= btn_y + btn_height):
                        target_button = btn
                        break
            
            # Swap positions if we found a target
            if target_button:
                self.app.swap_buttons(self.button_name, target_button.button_name)
            else:
                # Reset to grid position
                self.app.update_button_grid()
        
    def grid(self, *args, **kwargs):
        self.frame.grid(*args, **kwargs)
        
    def grid_remove(self):
        self.frame.grid_remove()

class App(ctk.CTk):
    def toggle_theme(self):
        # Toggle between light and dark
        current_mode = ctk.get_appearance_mode()
        new_mode = "Light" if current_mode == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self.settings.set('appearance_mode', new_mode.lower())
        
        # Update background image to match new theme
        if hasattr(self, 'bg_canvas'):
            self.update_background_image()
    
    def toggle_move_icons(self):
        """Toggle visibility of move icons on all buttons"""
        current_state = self.settings.get('show_move_icons', False)
        new_state = not current_state
        self.settings.set('show_move_icons', new_state)
        
        # Update all button move handles
        for btn in self.all_buttons:
            if hasattr(btn, 'move_handle'):
                if new_state:
                    btn.move_handle.place(relx=0.05, rely=0.05, anchor="nw")
                else:
                    btn.move_handle.place_forget()
    
    def toggle_auto_update_source2viewer(self):
        """Toggle auto-update for Source2Viewer"""
        current_state = self.settings.get('auto_update_source2viewer', True)
        new_state = not current_state
        self.settings.set('auto_update_source2viewer', new_state)
        
    def setup_window(self):
        # Configure window appearance
        self.title("CS2KZ Mapping Tools")
        self.geometry("340x400")  # Initial size
        self.resizable(False, False)
        
        # Set theme from settings
        appearance_mode = self.settings.get('appearance_mode', 'system')
        ctk.set_appearance_mode(appearance_mode)
    def toggle_button_no_close(self, button_name):
        """Toggle button visibility without closing the menu"""
        button = getattr(self, f"{button_name}_btn")
        var = self.button_vars[button_name]
        is_visible = var.get()
        
        # Update settings
        self.settings.set_button_visibility(button_name, is_visible)
        
        # Schedule the grid update for after the menu click
        self.after(1, lambda: self.update_grid_for_button(button_name, is_visible))
        
        # Keep the menu open by posting it again
        self.after(1, lambda: self.post_menu())
    
    def post_menu(self):
        """Re-post the view menu to keep it open"""
        menu_x = self.view_menu.winfo_rootx()
        menu_y = self.view_menu.winfo_rooty()
        if menu_x and menu_y:  # Only repost if we had a previous position
            self.view_menu.post(menu_x, menu_y)
    
    def update_grid_for_button(self, button_name, is_visible):
        """Update the grid for a specific button"""
        button = getattr(self, f"{button_name}_btn")
        if is_visible:
            self.update_button_grid()
        else:
            button.grid_remove()
            self.update_button_grid()

    def toggle_button_visibility(self, button_name):
        """Original toggle method for non-menu toggles"""
        button = getattr(self, f"{button_name}_btn")
        var = self.button_vars[button_name]
        is_visible = var.get()
        
        # Update settings
        self.settings.set_button_visibility(button_name, is_visible)
        
        # Update grid
        if is_visible:
            self.update_button_grid()
        else:
            button.grid_remove()
            self.update_button_grid()

    def swap_buttons(self, button1_name, button2_name):
        """Swap the order of two buttons"""
        button_order = self.settings.get_button_order()
        
        # Find indices of both buttons
        try:
            idx1 = button_order.index(button1_name)
            idx2 = button_order.index(button2_name)
            
            # Swap them
            button_order[idx1], button_order[idx2] = button_order[idx2], button_order[idx1]
            
            # Save new order
            self.settings.set_button_order(button_order)
            
            # Update the grid
            self.update_button_grid()
        except ValueError:
            # One of the buttons wasn't found in the order list
            print(f"Error: Could not find buttons {button1_name} or {button2_name} in order list")

    def update_button_grid(self, event=None):
        # Get button order from settings
        button_order = self.settings.get_button_order()
        visible_buttons_dict = self.settings.get_visible_buttons()
        
        # Create ordered list of visible buttons
        visible_buttons = []
        for name in button_order:
            if visible_buttons_dict.get(name, False):
                btn = getattr(self, f"{name}_btn", None)
                if btn:
                    visible_buttons.append(btn)
        
        # Calculate window size FIRST with fixed row heights
        num_rows = (len(visible_buttons) + 1) // 2 if len(visible_buttons) > 0 else 1
        window_width = 308  # 440 * 0.7 = 308
        
        # Fixed heights for each row configuration (menu bar + content + consistent padding)
        # Breakdown:
        # - Menu bar: 42px
        # - Top padding from main_frame: 14px
        # - Each button row: 126px (button frame) + 7px (top grid padding) + 7px (bottom grid padding) = 140px
        # - Bottom padding: 7px (to match top padding, since grid already adds 7px below last row)
        menu_bar_height = 42  # Menu bar height
        top_padding = 14  # Top padding from main_frame
        row_height = 140  # Height per row (126 frame + 7 top + 7 bottom padding)
        bottom_padding = 0  # :3
        
        window_height = menu_bar_height + top_padding + (num_rows * row_height) + bottom_padding
        
        # Get current position AFTER calculating size
        current_x = self.winfo_x()
        current_y = self.winfo_y()
        
        # Set geometry BEFORE modifying grid to prevent auto-resizing
        if not hasattr(self, 'initial_position_set'):
            # Get saved position from settings
            saved_pos = self.settings.get_window_position()
            if saved_pos:
                x, y = saved_pos
            else:
                # Center window if no saved position
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
            
            self.geometry(f"{window_width}x{window_height}+{x}+{y}")
            self.minsize(window_width, window_height)
            self.maxsize(window_width, window_height)
            self.initial_position_set = True
        else:
            # Set geometry BEFORE grid operations to lock the size
            self.geometry(f"{window_width}x{window_height}+{current_x}+{current_y}")
            self.minsize(window_width, window_height)
            self.maxsize(window_width, window_height)
            self.settings.set_window_position(current_x, current_y)
        
        # Force geometry update to apply immediately
        self.update_idletasks()
        
        # NOW modify the grid
        # CRITICAL: Remove all buttons from both grid AND place geometry
        for btn in self.all_buttons:
            btn.frame.place_forget()  # Clear any place geometry first
            btn.grid_remove()  # Then remove from grid
        
        # Redistribute visible buttons in a 2-column grid
        for i, btn in enumerate(visible_buttons):
            row = i // 2
            col = i % 2
            btn.grid(row=row, column=col, padx=(7, 7), pady=(7, 7), sticky="nsew")  # 10 * 0.7 = 7
        
        # Update background only if window height actually changed
        if not hasattr(self, '_last_window_height') or self._last_window_height != window_height:
            self.after(100, self.update_background_image)
            self._last_window_height = window_height

    def configure_menu_colors(self, menu_widget):
        # Get colors from CustomTkinter theme
        is_dark = ctk.get_appearance_mode() == "Dark"
        
        # Use semi-dark colors to blend with background
        bg_color = "#2a2a2a" if is_dark else "#e0e0e0"
        fg_color = "white" if is_dark else "black"
        active_bg = "#3a3a3a" if is_dark else "#d0d0d0"
        
        menu_widget.configure(
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            selectcolor=fg_color,
            borderwidth=0,
            relief="flat"
        )
        
        # Apply to submenus
        for item in menu_widget.winfo_children():
            if isinstance(item, tk.Menu):
                self.configure_menu_colors(item)

    def open_github(self):
        """Open the GitHub project page"""
        import webbrowser
        import threading
        # Use threading to avoid GIL issues with webbrowser
        threading.Thread(target=lambda: webbrowser.open("https://github.com/jakkekz/.jakke"), daemon=True).start()

    def open_theme_config(self):
        """Open theme configuration in temp directory"""
        import os
        import webbrowser
        temp_dir = os.path.join(os.environ.get('TEMP', '/temp'))
        config_path = os.path.join(temp_dir, 'theme_config.json')
        
        # Create config file if it doesn't exist
        if not os.path.exists(config_path):
            import json
            default_config = {
                'theme': ctk.get_appearance_mode().lower(),
                'color_theme': 'blue'
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
        
        # Open the file
        os.startfile(config_path)

    def create_menu(self):
        # Get colors from CustomTkinter theme
        is_dark = ctk.get_appearance_mode() == "Dark"
        
        # Use semi-dark colors to blend with background
        bg_color = "#2a2a2a" if is_dark else "#e0e0e0"
        fg_color = "white" if is_dark else "black"
        active_bg = "#3a3a3a" if is_dark else "#d0d0d0"
        
        # Create menu with transparent-like colors
        self.menubar = tk.Menu(self,
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color,
            selectcolor=fg_color,
            borderwidth=0,
            relief="flat"
        )
        self.config(menu=self.menubar)

        # Create View menu for button visibility
        self.view_menu = tk.Menu(self.menubar, tearoff=0)  # Disable tearoff
        self.configure_menu_colors(self.view_menu)
        self.menubar.add_cascade(label="View", menu=self.view_menu)
        
        # Add checkbuttons for each button's visibility
        button_labels = {
            "dedicated_server": "Dedicated Server",
            "insecure": "Insecure",
            "listen": "Listen",
            "mapping": "Mapping",
            "source2viewer": "Source2 Viewer"
        }
        
        # Initialize button variables from settings
        self.button_vars = {}
        saved_visibility = self.settings.get_visible_buttons()
        
        for button_name, label in button_labels.items():
            self.button_vars[button_name] = tk.BooleanVar(value=saved_visibility.get(button_name, True))
            # Modify the command to prevent menu from closing
            self.view_menu.add_checkbutton(
                label=label,
                variable=self.button_vars[button_name],
                command=lambda name=button_name: self.toggle_button_no_close(name)
            )

        # Create Settings menu
        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.configure_menu_colors(self.settings_menu)
        self.menubar.add_cascade(label="Settings", menu=self.settings_menu)
        
        # Add toggle theme to settings
        self.settings_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        self.settings_menu.add_separator()
        
        # Add move icons toggle
        self.show_move_icons_var = tk.BooleanVar(value=self.settings.get('show_move_icons', False))
        self.settings_menu.add_checkbutton(
            label="Show Move Icons",
            variable=self.show_move_icons_var,
            command=self.toggle_move_icons
        )
        
        # Add auto-update Source2Viewer toggle
        self.auto_update_s2v_var = tk.BooleanVar(value=self.settings.get('auto_update_source2viewer', True))
        self.settings_menu.add_checkbutton(
            label="Auto Update Source2Viewer",
            variable=self.auto_update_s2v_var,
            command=self.toggle_auto_update_source2viewer
        )
        
        # Add GitHub button to menubar next to Settings
        self.menubar.add_command(label="Github", command=self.open_github)

    def set_source2viewer_path(self):
        """Open file dialog to set Source2Viewer.exe path"""
        file_path = filedialog.askopenfilename(
            title="Select Source2Viewer.exe",
            filetypes=[("Executable files", "*.exe")]
        )
        if file_path:
            self.settings.set('source2viewer_path', file_path)

    def source2viewer_click(self):
        """Handler for Source2Viewer button - runs S2V-AUL.py script or launches directly"""
        auto_update = self.settings.get('auto_update_source2viewer', True)
        
        if auto_update:
            # Run the update script
            script_path = "S2V-AUL.py"
            if os.path.exists(script_path):
                try:
                    subprocess.Popen([sys.executable, script_path])
                except Exception as e:
                    print(f"Error running S2V-AUL.py: {e}")
            else:
                print(f"Warning: {script_path} not found in the current directory")
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

    def __init__(self):
        # Initialize settings manager first
        self.settings = SettingsManager()
        
        # Initialize base class with theme settings
        super().__init__()
        
        # Set appearance mode from settings
        appearance_mode = self.settings.get('appearance_mode', 'system')
        ctk.set_appearance_mode(appearance_mode)
        
        # Set color theme from settings
        color_theme = self.settings.get('color_theme', 'blue')
        ctk.set_default_color_theme(color_theme)
        
        # Configure window
        self.title("CS2KZ Mapping Tools")
        self.resizable(False, False)
        
        # CRITICAL: Prevent window from auto-resizing based on content
        self.grid_propagate(False)
        
        # Set background image using Canvas
        try:
            from PIL import Image, ImageTk
            # Create canvas for background that fills the window
            self.bg_canvas = tk.Canvas(self, highlightthickness=0, bd=0)
            self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_photo = None
        except Exception as e:
            print(f"Error loading background image: {e}")
        
        # Create main frame with transparent background so bg1.jpg shows through
        self.main_frame = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color="transparent"  # Transparent to show background image
        )
        self.main_frame.grid(row=0, column=0, padx=(14, 14), pady=(14, 14), sticky="nsew")  # 20 * 0.7 = 14
        
        # Configure grid spacing with equal padding
        self.grid_columnconfigure(0, weight=1)  # Center the main frame
        self.main_frame.grid_columnconfigure(0, weight=1, pad=7)  # 10 * 0.7 = 7
        self.main_frame.grid_columnconfigure(1, weight=1, pad=7)  # 10 * 0.7 = 7
        for i in range(3):  # Support up to 3 rows
            self.main_frame.grid_rowconfigure(i, weight=1, pad=7)  # 10 * 0.7 = 7
        
        # Set custom icon
        try:
            self.iconbitmap(os.path.join("icons", "hammerkz.ico"))
        except tk.TclError:
            print("Warning: icons/hammerkz.ico not found in the current directory")
        
        # Create menu bar (after main_frame creation)
        self.create_menu()

        # Configure frame grid columns for fixed button sizes
        self.main_frame.grid_columnconfigure(0, minsize=105)  # 150 * 0.7 = 105
        self.main_frame.grid_columnconfigure(1, minsize=105)  # 150 * 0.7 = 105

        # Create all buttons
        self.dedicated_server_btn = RoundedButton(
            self.main_frame, 
            text="Dedicated\nServer",
            command=self.dedicated_server_click,
            image_path=os.path.join("icons", "icondedicated.ico") if os.path.exists(os.path.join("icons", "icondedicated.ico")) else None,
            button_name="dedicated_server",
            app=self
        )
        
        self.insecure_btn = RoundedButton(
            self.main_frame, 
            text="Insecure",
            command=self.insecure_click,
            image_path=os.path.join("icons", "iconinsecure.ico") if os.path.exists(os.path.join("icons", "iconinsecure.ico")) else None,
            button_name="insecure",
            app=self
        )
        
        self.listen_btn = RoundedButton(
            self.main_frame, 
            text="Listen",
            command=self.listen_click,
            image_path=os.path.join("icons", "iconlisten.ico") if os.path.exists(os.path.join("icons", "iconlisten.ico")) else None,
            button_name="listen",
            app=self
        )
        
        self.mapping_btn = RoundedButton(
            self.main_frame, 
            text="Mapping",
            command=self.mapping_click,
            image_path=os.path.join("icons", "hammerkz.ico") if os.path.exists(os.path.join("icons", "hammerkz.ico")) else None,
            button_name="mapping",
            app=self
        )
        
        self.source2viewer_btn = RoundedButton(
            self.main_frame, 
            text="Source2Viewer",
            command=self.source2viewer_click,
            image_path=os.path.join("icons", "source2viewer.ico") if os.path.exists(os.path.join("icons", "source2viewer.ico")) else None,
            settings_command=self.set_source2viewer_path,
            grid_column=1,  # Assuming Source2Viewer is in the right column
            button_name="source2viewer",
            app=self
        )
        
        # Store all buttons in a list for easy management
        self.all_buttons = [
            self.dedicated_server_btn,
            self.insecure_btn,
            self.listen_btn,
            self.mapping_btn,
            self.source2viewer_btn
        ]
        
        # Bind window close event to save settings
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Create menu bar and buttons
        self.create_menu()
        
        # Apply initial layout
        self.update_button_grid()
        
        # Update background image after window is sized
        if hasattr(self, 'bg_canvas') and os.path.exists(os.path.join("icons", "bg1.jpg")):
            self.after(100, self.update_background_image)
    
    def update_background_image(self):
        """Update the background image to match window width and theme"""
        try:
            from PIL import Image, ImageTk
            
            # Select background image based on theme
            is_dark = ctk.get_appearance_mode() == "Dark"
            bg_file = os.path.join("icons", "bg1dark.jpg") if is_dark else os.path.join("icons", "bg1light.jpg")
            
            # Check if the theme-specific image exists, fallback to bg1dark.jpg
            if not os.path.exists(bg_file):
                bg_file = os.path.join("icons", "bg1dark.jpg")
                if not os.path.exists(bg_file):
                    print(f"Warning: No background image found (tried icons/bg1dark.jpg, icons/bg1light.jpg)")
                    return
            
            bg_image = Image.open(bg_file)
            
            window_width = self.winfo_width()
            window_height = self.winfo_height()
            
            if window_width > 1 and window_height > 1:  # Ensure valid dimensions
                # Get original image dimensions
                original_width, original_height = bg_image.size
                
                # Scale only based on width, maintain aspect ratio
                scale_factor = window_width / original_width
                new_width = window_width
                new_height = int(original_height * scale_factor)
                
                # Resize image
                bg_image = bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.bg_photo = ImageTk.PhotoImage(bg_image)
                
                # Clear canvas and add image from the bottom
                self.bg_canvas.delete("all")
                self.bg_canvas.create_image(0, window_height, image=self.bg_photo, anchor="sw")
                
                print(f"Background image loaded: {bg_file} - {new_width}x{new_height} (window: {window_width}x{window_height})")
            else:
                # Retry if window isn't sized yet
                self.after(100, self.update_background_image)
        except Exception as e:
            print(f"Error updating background image: {e}")

    def set_source2viewer_path(self):
        """Open file dialog to set Source2Viewer.exe path"""
        file_path = filedialog.askopenfilename(
            title="Select Source2Viewer.exe",
            filetypes=[("Executable files", "*.exe")]
        )
        if file_path:
            self.settings.set('source2viewer_path', file_path)

    def on_closing(self):
        # Save current window position
        self.settings.set_window_position(self.winfo_x(), self.winfo_y())
        
        # Save current button visibility states
        for name, var in self.button_vars.items():
            self.settings.set_button_visibility(name, var.get())
            
        # Destroy the window
        self.destroy()

    def dedicated_server_click(self):
        """Handler for dedicated server button"""
        print("Dedicated Server clicked")

    def insecure_click(self):
        """Handler for insecure button"""
        print("Insecure clicked")

    def listen_click(self):
        """Handler for listen button"""
        print("Listen clicked")

    def mapping_click(self):
        """Handler for mapping button"""
        print("Mapping clicked")

    def open_config_directory(self):
        """Opens the directory containing the config file"""
        import os
        import subprocess
        config_path = self.settings.settings_file
        config_dir = os.path.dirname(config_path)
        # Use explorer to open the directory
        subprocess.run(['explorer', config_dir])

if __name__ == "__main__":
    app = App()
    app.mainloop()