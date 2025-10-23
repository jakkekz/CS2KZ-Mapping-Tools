"""
VTF to PNG Converter - GUI Version
Allows user to select multiple VTF files and converts them to PNG
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import os
import sys

# Try to import VTF support
try:
    from vtf2img import Parser
    VTF_SUPPORT = True
except ImportError:
    VTF_SUPPORT = False
    print("Warning: vtf2img library not found. VTF conversion will not work.")
    print("Install with: pip install vtf2img")


def convert_vtf_to_png(vtf_path, output_path=None):
    """
    Convert a single VTF file to PNG.
    
    Args:
        vtf_path: Path to the VTF file
        output_path: Optional output path. If None, uses same directory with .png extension
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not VTF_SUPPORT:
        return False, "vtf2img library is not installed"
    
    try:
        # Parse VTF file
        parser = Parser(vtf_path)
        image = parser.get_image()
        
        # Ensure RGBA format
        image = image.convert("RGBA")
        
        # Determine output path
        if output_path is None:
            output_path = os.path.splitext(vtf_path)[0] + '.png'
        
        # Save as PNG
        image.save(output_path, "PNG")
        return True, output_path
        
    except Exception as e:
        if "Unknown image format 3" in str(e):
            return False, f"Rare compression format (Type 3) not supported.\nUse VTFEdit to export manually."
        return False, f"Conversion error: {str(e)}"


def select_vtf_files():
    """Open dialog to select VTF files"""
    root = tk.Tk()
    root.withdraw()
    
    file_paths = filedialog.askopenfilenames(
        title="Select VTF files to convert",
        filetypes=[
            ("VTF files", "*.vtf"),
            ("All files", "*.*")
        ]
    )
    
    if not file_paths:
        return None
    
    return list(file_paths)


def select_output_directory():
    """Open dialog to select output directory"""
    root = tk.Tk()
    root.withdraw()
    
    dir_path = filedialog.askdirectory(
        title="Select output directory (or Cancel to use same directory as VTF files)"
    )
    
    return dir_path if dir_path else None


def convert_files(vtf_files, output_dir=None):
    """
    Convert multiple VTF files to PNG.
    
    Args:
        vtf_files: List of VTF file paths
        output_dir: Optional output directory. If None, saves next to original files
    
    Returns:
        tuple: (converted_count, failed_count, results_list, actual_output_dir)
    """
    converted = 0
    failed = 0
    results = []
    actual_output_dir = output_dir
    
    for vtf_file in vtf_files:
        filename = os.path.basename(vtf_file)
        
        # Determine output path
        if output_dir:
            output_filename = os.path.splitext(filename)[0] + '.png'
            output_path = os.path.join(output_dir, output_filename)
        else:
            output_path = None  # Will use same directory as VTF
            # Track the actual output directory from first file
            if actual_output_dir is None:
                actual_output_dir = os.path.dirname(vtf_file)
        
        # Convert
        success, message = convert_vtf_to_png(vtf_file, output_path)
        
        if success:
            converted += 1
            results.append(f"✓ {filename} -> {os.path.basename(message)}")
        else:
            failed += 1
            results.append(f"✗ {filename}: {message}")
    
    return converted, failed, results, actual_output_dir


def main():
    """Main function"""
    # Check if VTF support is available
    if not VTF_SUPPORT:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Library",
            "vtf2img library is not installed.\n\n"
            "Please install it with:\n"
            "pip install vtf2img"
        )
        sys.exit(1)
    
    # Select VTF files
    vtf_files = select_vtf_files()
    if not vtf_files:
        sys.exit(0)
    
    # Ask about output directory
    root = tk.Tk()
    root.withdraw()
    
    use_custom_dir = messagebox.askyesno(
        "Output Location",
        f"Selected {len(vtf_files)} VTF file(s).\n\n"
        "Save PNG files to a different directory?\n\n"
        "Yes = Choose output directory\n"
        "No = Save next to VTF files"
    )
    
    output_dir = None
    if use_custom_dir:
        output_dir = select_output_directory()
        if not output_dir:
            # User cancelled directory selection
            messagebox.showinfo("Cancelled", "Output directory selection cancelled.\nUsing same directory as VTF files.")
    
    # Convert files
    converted, failed, results, actual_output_dir = convert_files(vtf_files, output_dir)
    
    # Show results
    root = tk.Tk()
    root.withdraw()
    
    result_text = "\n".join(results)
    summary = f"Conversion Complete!\n\nConverted: {converted}\nFailed: {failed}\n\n{result_text}"
    
    if failed > 0:
        messagebox.showwarning("Conversion Complete (with errors)", summary)
    else:
        messagebox.showinfo("Success", summary)
    
    # Open output directory if any files were converted
    if converted > 0 and actual_output_dir:
        try:
            if sys.platform == 'win32':
                os.startfile(actual_output_dir)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{actual_output_dir}"')
            else:  # linux
                os.system(f'xdg-open "{actual_output_dir}"')
        except Exception:
            pass


if __name__ == "__main__":
    main()
