"""
Loading Screen Creator - GUI Version
Creates loading screen images and map icons for CS2 maps
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import subprocess
from pathlib import Path

# Import the creator functions
from creator import (
    get_cs2_path,
    create_vmat_content,
    compile_vmat_files,
    compile_svg_files,
    Image
)


class LoadingScreenCreatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CS2 Loading Screen Creator")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        # Variables
        self.map_name = tk.StringVar()
        self.image_files = []
        self.svg_file = None
        self.txt_file = None
        self.cs2_path = None
        
        # Try to find CS2 path automatically
        self.cs2_path = get_cs2_path()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title = tk.Label(self.root, text="CS2 Loading Screen Creator", 
                        font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Map Name
        name_frame = tk.Frame(self.root)
        name_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(name_frame, text="Map Name:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        tk.Entry(name_frame, textvariable=self.map_name, font=("Arial", 10)).pack(fill=tk.X, pady=5)
        tk.Label(name_frame, text="Example: kz_jakke", font=("Arial", 8), 
                fg="gray").pack(anchor=tk.W)
        
        # Images Section
        images_frame = tk.Frame(self.root)
        images_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(images_frame, text="Loading Screen Images (1-9, optional):", 
                font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        btn_frame = tk.Frame(images_frame)
        btn_frame.pack(pady=5, fill=tk.X)
        
        tk.Button(btn_frame, text="Select Images", command=self.select_images,
                 bg="#4CAF50", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Clear Images", command=self.clear_images,
                 bg="#f44336", fg="white", font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Images listbox
        listbox_frame = tk.Frame(images_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.images_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set,
                                         height=6, font=("Arial", 9))
        self.images_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.images_listbox.yview)
        
        # SVG Icon Section
        svg_frame = tk.Frame(self.root)
        svg_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(svg_frame, text="Map Icon (SVG, optional):", 
                font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        svg_btn_frame = tk.Frame(svg_frame)
        svg_btn_frame.pack(pady=5, fill=tk.X)
        
        tk.Button(svg_btn_frame, text="Select SVG", command=self.select_svg,
                 bg="#2196F3", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        
        self.svg_label = tk.Label(svg_btn_frame, text="No file selected", 
                                  font=("Arial", 9), fg="gray")
        self.svg_label.pack(side=tk.LEFT, padx=5)
        
        # Description Text Section
        txt_frame = tk.Frame(self.root)
        txt_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(txt_frame, text="Map Description (TXT, optional):", 
                font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        txt_btn_frame = tk.Frame(txt_frame)
        txt_btn_frame.pack(pady=5, fill=tk.X)
        
        tk.Button(txt_btn_frame, text="Select TXT", command=self.select_txt,
                 bg="#2196F3", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        
        self.txt_label = tk.Label(txt_btn_frame, text="No file selected", 
                                  font=("Arial", 9), fg="gray")
        self.txt_label.pack(side=tk.LEFT, padx=5)
        
        # Create Button
        create_btn = tk.Button(self.root, text="Create Loading Screen Files", 
                              command=self.create_files,
                              bg="#FF9800", fg="white", font=("Arial", 11, "bold"),
                              height=2)
        create_btn.pack(pady=20, padx=20, fill=tk.X)
    
    def select_images(self):
        files = filedialog.askopenfilenames(
            title="Select Loading Screen Images (1-9 images)",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.tga *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if files:
            # Limit to 9 images
            files = list(files)[:9]
            self.image_files = files
            
            # Update listbox
            self.images_listbox.delete(0, tk.END)
            for i, file in enumerate(files, 1):
                self.images_listbox.insert(tk.END, f"{i}. {os.path.basename(file)}")
    
    def clear_images(self):
        self.image_files = []
        self.images_listbox.delete(0, tk.END)
    
    def select_svg(self):
        file = filedialog.askopenfilename(
            title="Select Map Icon (SVG)",
            filetypes=[
                ("SVG files", "*.svg"),
                ("All files", "*.*")
            ]
        )
        
        if file:
            self.svg_file = file
            self.svg_label.config(text=os.path.basename(file), fg="black")
    
    def select_txt(self):
        file = filedialog.askopenfilename(
            title="Select Map Description (TXT)",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if file:
            self.txt_file = file
            self.txt_label.config(text=os.path.basename(file), fg="black")
    
    def create_files(self):
        # Validate map name
        if not self.map_name.get().strip():
            messagebox.showerror("Error", "Please enter a map name!")
            return
        
        map_name = self.map_name.get().strip()
        
        # Check if CS2 path is found
        if not self.cs2_path:
            messagebox.showerror(
                "CS2 Not Found",
                "Could not automatically find CS2 installation.\n\n"
                "Please make sure Counter-Strike 2 is installed via Steam."
            )
            return
        
        try:
            # Define the base paths
            content_addons_dir = os.path.join(self.cs2_path, 'content', 'csgo_addons', map_name)
            game_addons_dir = os.path.join(self.cs2_path, 'game', 'csgo_addons', map_name)
            
            # Define full destination folder paths
            loading_screen_dir = os.path.join(content_addons_dir, 'panorama', 'images', 'map_icons', 'screenshots', '1080p')
            map_icon_content_dir = os.path.join(content_addons_dir, 'panorama', 'images', 'map_icons')
            maps_dir = os.path.join(game_addons_dir, 'maps')
            
            # Create destination directories
            for directory in [loading_screen_dir, map_icon_content_dir, maps_dir]:
                os.makedirs(directory, exist_ok=True)
            
            vmat_files_to_compile = []
            svg_files_to_compile = []
            
            # Process images
            if self.image_files:
                for i, source_image_path in enumerate(self.image_files, 1):
                    dest_image_name = f"{map_name}_{i}_png.png"
                    dest_image_path = os.path.join(loading_screen_dir, dest_image_name)
                    
                    # Crop to 16:9 and save
                    with Image.open(source_image_path) as img:
                        width, height = img.size
                        
                        # Calculate new dimensions for 16:9 aspect ratio
                        target_aspect_ratio = 16.0 / 9.0
                        original_aspect_ratio = width / height
                        
                        if original_aspect_ratio > target_aspect_ratio:
                            # Image is too wide, crop the sides
                            new_width = int(height * target_aspect_ratio)
                            left = (width - new_width) / 2
                            top = 0
                            right = (width + new_width) / 2
                            bottom = height
                        else:
                            # Image is too tall, crop the top and bottom
                            new_height = int(width / target_aspect_ratio)
                            left = 0
                            top = (height - new_height) / 2
                            right = width
                            bottom = (height + new_height) / 2
                        
                        # Crop and save
                        img_cropped = img.crop((left, top, right, bottom))
                        img_cropped.save(dest_image_path, "PNG")
                    
                    # Generate corresponding vmat file
                    dest_vmat_name = f"{map_name}_{i}_png.vmat"
                    dest_vmat_path = os.path.join(loading_screen_dir, dest_vmat_name)
                    vmat_content = create_vmat_content(map_name, i)
                    
                    with open(dest_vmat_path, 'w') as f:
                        f.write(vmat_content)
                    
                    vmat_files_to_compile.append(dest_vmat_path)
            
            # Process SVG
            if self.svg_file:
                import shutil
                dest_icon_name = f"map_icon_{map_name}.svg"
                dest_icon_path = os.path.join(map_icon_content_dir, dest_icon_name)
                shutil.copy(self.svg_file, dest_icon_path)
                svg_files_to_compile.append(dest_icon_path)
            
            # Process TXT
            if self.txt_file:
                import shutil
                description_file_name = f"{map_name}.txt"
                description_file_path = os.path.join(maps_dir, description_file_name)
                shutil.copy(self.txt_file, description_file_path)
            
            # Compile VMAT files
            if vmat_files_to_compile:
                compile_vmat_files(self.cs2_path, vmat_files_to_compile, map_name)
            
            # Compile SVG files
            if svg_files_to_compile:
                compile_svg_files(self.cs2_path, svg_files_to_compile, map_name)
            
            messagebox.showinfo(
                "Success",
                f"Loading screen files created successfully for {map_name}!\n\n"
                f"Images: {len(self.image_files)}\n"
                f"SVG Icon: {'Yes' if self.svg_file else 'No'}\n"
                f"Description: {'Yes' if self.txt_file else 'No'}\n\n"
                f"Files have been compiled and placed in:\n"
                f"game/csgo_addons/{map_name}/"
            )
            
            # Open the output folder
            try:
                os.startfile(game_addons_dir)
            except Exception:
                pass
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")


def main():
    root = tk.Tk()
    app = LoadingScreenCreatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
