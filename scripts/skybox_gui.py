"""
GUI Skybox Converter - Simplified version with file dialogs
Allows user to select 6 skybox images and output location
Supports VTF, PNG, JPG, TGA formats
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import os
import sys
import tempfile

# Try to import VTF support
try:
    from vtf2img import Parser
    VTF_SUPPORT = True
except ImportError:
    VTF_SUPPORT = False
    print("Warning: vtf2img library not found. VTF files will not be supported.")
    print("Install with: pip install vtf2img")

# Face order for the skybox
TARGET_SLOTS = ['up', 'left', 'front', 'right', 'back', 'down']

# Transformation configuration for standard VTF/PNG files
# Format: 'Target Slot': ('Source Face', Rotation Degrees (CCW), PIL Flip Constant)
DEFAULT_TRANSFORMS = {
    'up':      ('up', 0, None),
    'down':    ('down', 0, None),
    'left':    ('back', 0, None), 
    'front':   ('right', 0, None),
    'right':   ('front', 0, None), 
    'back':    ('left', 0, None),
}

def select_skybox_files():
    """Open dialog to select all 6 skybox face images at once"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Show instructions
    messagebox.showinfo(
        "Select Skybox Files",
        "Please select all 6 skybox face images.\n\n"
        "Images must be named with these face identifiers:\n\n"
        "• UP: _up, up_, up.\n"
        "• DOWN: _down, down_, down., _dn, dn_, dn.\n"
        "• LEFT: _left, left_, left., _lf, lf_, lf.\n"
        "• RIGHT: _right, right_, right., _rt, rt_, rt.\n"
        "• FRONT: _front, front_, front., _ft, ft_, ft.\n"
        "• BACK: _back, back_, back., _bk, bk_, bk.\n\n"
        "Supported formats: PNG, JPG, TGA, VTF"
    )
    
    # Ask user to select all 6 files at once
    file_paths = filedialog.askopenfilenames(
        title="Select all 6 skybox face images",
        filetypes=[
            ("Image files", "*.png *.jpg *.jpeg *.tga *.vtf"),
            ("All files", "*.*")
        ]
    )
    
    if not file_paths:
        messagebox.showerror("Cancelled", "No files selected. Aborting.")
        return None
    
    if len(file_paths) != 6:
        messagebox.showerror("Invalid Selection", f"Please select exactly 6 images. You selected {len(file_paths)}.")
        return None
    
    # Try to automatically match files to faces based on filename
    files = {}
    unmatched_files = []
    
    for file_path in file_paths:
        filename = os.path.basename(file_path).lower()
        matched = False
        
        for face in TARGET_SLOTS:
            # Common abbreviations for each face
            face_patterns = {
                'up': ['_up.', 'up.', '_up_', 'up_'],
                'down': ['_down.', 'down.', '_down_', 'down_', '_dn.', 'dn.', '_dn_', 'dn_'],
                'left': ['_left.', 'left.', '_left_', 'left_', '_lf.', 'lf.', '_lf_', 'lf_'],
                'right': ['_right.', 'right.', '_right_', 'right_', '_rt.', 'rt.', '_rt_', 'rt_'],
                'front': ['_front.', 'front.', '_front_', 'front_', '_ft.', 'ft.', '_ft_', 'ft_'],
                'back': ['_back.', 'back.', '_back_', 'back_', '_bk.', 'bk.', '_bk_', 'bk_']
            }
            
            patterns = face_patterns.get(face, [])
            
            if any(pattern in filename for pattern in patterns):
                if face in files:
                    # Duplicate face found
                    messagebox.showerror(
                        "Duplicate Face",
                        f"Multiple files detected for '{face}' face.\nPlease ensure each face has only one image."
                    )
                    return None
                files[face] = file_path
                matched = True
                break
        
        if not matched:
            unmatched_files.append(os.path.basename(file_path))
    
    # Check if we matched all 6 faces
    if len(files) != 6:
        missing_faces = [face for face in TARGET_SLOTS if face not in files]
        messagebox.showerror(
            "Cannot Auto-Detect Faces",
            f"Could not automatically detect which image corresponds to which skybox face.\n\n"
            f"Matched: {len(files)}/6 faces\n"
            f"Missing: {', '.join(missing_faces)}\n"
            f"Unmatched files: {', '.join(unmatched_files) if unmatched_files else 'None'}\n\n"
            f"Please ensure your files are named with face indicators:\n"
            f"Examples: skybox_up.png, left.tga, mysky_front.jpg, etc."
        )
        return None
    
    return files

def select_output_location():
    """Open dialog to select output file location"""
    root = tk.Tk()
    root.withdraw()
    
    file_path = filedialog.asksaveasfilename(
        title="Save Skybox As",
        defaultextension=".png",
        filetypes=[("PNG Image", "*.png")]
    )
    
    if not file_path:
        messagebox.showerror("Cancelled", "No output location selected. Aborting.")
        return None
    
    return file_path

def convert_vtf_to_pil_image(vtf_path):
    """
    Converts a VTF file to a PIL Image object.
    Returns the Image or raises an exception.
    """
    if not VTF_SUPPORT:
        raise ImportError("vtf2img library is not installed. Cannot convert VTF files.")
    
    try:
        parser = Parser(vtf_path)
        image = parser.get_image()
        # Ensure image is in RGBA format
        image = image.convert("RGBA")
        return image
    except Exception as e:
        if "Unknown image format 3" in str(e):
            raise Exception(
                f"This VTF uses a rare compression format (Type 3) that is not supported.\n"
                f"Please use VTFEdit to manually export '{os.path.basename(vtf_path)}' to PNG/TGA."
            )
        raise Exception(f"Error converting VTF file '{os.path.basename(vtf_path)}': {e}")

def stitch_skybox(files, output_path):
    """Stitch the 6 faces into a single skybox image with proper transformations"""
    temp_files = []  # Track temporary files for cleanup
    
    try:
        # Load all images (convert VTF if needed)
        images = {}
        base_size = None
        
        for face, path in files.items():
            # Check if it's a VTF file
            if path.lower().endswith('.vtf'):
                if not VTF_SUPPORT:
                    raise ImportError(
                        "VTF files detected but vtf2img library is not installed.\n"
                        "Please install it with: pip install vtf2img"
                    )
                print(f"Converting VTF file: {os.path.basename(path)}")
                img = convert_vtf_to_pil_image(path)
            else:
                img = Image.open(path).convert("RGBA")
            
            images[face] = img
            
            # Use the first image size as base size
            if base_size is None:
                base_size = img.size[0]  # Assuming square images
        
        # Create the final image (4x3 grid)
        final_width = base_size * 4
        final_height = base_size * 3
        final_image = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
        
        # Coordinates for each face in the 4x3 grid
        COORDS = {
            'up':    (base_size * 1, base_size * 0),
            'left':  (base_size * 0, base_size * 1),
            'front': (base_size * 1, base_size * 1),
            'right': (base_size * 2, base_size * 1),
            'back':  (base_size * 3, base_size * 1),
            'down':  (base_size * 1, base_size * 2),
        }
        
        print("\nStitching images with proper transformations...")
        
        # Loop over target slots and apply transformations
        for target_slot in TARGET_SLOTS:
            # Get transformation from DEFAULT_TRANSFORMS
            source_face, rotation_degrees, flip = DEFAULT_TRANSFORMS.get(target_slot, (target_slot, 0, None))
            
            # Get the source image
            image_to_paste = images[source_face]
            
            # Resize to base size if needed
            if image_to_paste.size[0] != base_size:
                image_to_paste = image_to_paste.resize((base_size, base_size), Image.Resampling.LANCZOS)
            
            # Apply rotation if specified
            if rotation_degrees != 0:
                image_to_paste = image_to_paste.rotate(rotation_degrees, expand=False)
            
            # Apply flip/transpose if specified
            if flip is not None:
                image_to_paste = image_to_paste.transpose(flip)
            
            # Paste into final image at correct position
            position = COORDS[target_slot]
            final_image.paste(image_to_paste, position)
            
            print(f"  {target_slot}: source='{source_face}', rotation={rotation_degrees}°")
        
        # Save the final image
        final_image.save(output_path, "PNG")
        
        return True, f"Skybox saved successfully to:\n{output_path}\n\nResolution: {final_width}x{final_height}"
        
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error creating skybox: {str(e)}"

def main():
    """Main function"""
    # Select the 6 skybox faces
    files = select_skybox_files()
    if not files:
        sys.exit(1)
    
    # Select output location
    output_path = select_output_location()
    if not output_path:
        sys.exit(1)
    
    # Stitch the skybox
    success, message = stitch_skybox(files, output_path)
    
    # Show result
    root = tk.Tk()
    root.withdraw()
    
    if success:
        messagebox.showinfo("Success", message)
        # Open the folder containing the output image
        try:
            output_folder = os.path.dirname(output_path)
            if sys.platform == 'win32':
                os.startfile(output_folder)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{output_folder}"')
            else:  # linux
                os.system(f'xdg-open "{output_folder}"')
        except Exception as e:
            print(f"Could not open output folder: {e}")
    else:
        messagebox.showerror("Error", message)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
