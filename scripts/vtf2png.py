"""
VTF to PNG Converter
Converts all VTF files in the current directory to PNG format
"""

import os
import sys
from pathlib import Path

# Try to import VTF support
try:
    from vtf2img import Parser
except ImportError:
    print("Error: vtf2img library is required.")
    print("Install it with: pip install vtf2img")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow library is required.")
    print("Install it with: pip install Pillow")
    sys.exit(1)


def convert_vtf_to_png(vtf_path, output_path=None):
    """
    Convert a single VTF file to PNG.
    
    Args:
        vtf_path: Path to the VTF file
        output_path: Optional output path. If None, uses same directory with .png extension
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Parse VTF file
        parser = Parser(vtf_path)
        image = parser.get_image()
        
        # Ensure RGBA format
        image = image.convert("RGBA")
        
        # Determine output path
        if output_path is None:
            output_path = Path(vtf_path).with_suffix('.png')
        
        # Save as PNG
        image.save(output_path, "PNG")
        return True
        
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    """Main function - convert all VTF files in current directory"""
    # Get current directory
    current_dir = Path.cwd()
    
    # Find all VTF files
    vtf_files = list(current_dir.glob("*.vtf"))
    
    if not vtf_files:
        print("No VTF files found in the current directory.")
        return
    
    print(f"Found {len(vtf_files)} VTF file(s)")
    print("-" * 50)
    
    converted = 0
    failed = 0
    
    for vtf_file in vtf_files:
        print(f"Converting: {vtf_file.name}")
        
        if convert_vtf_to_png(vtf_file):
            output_name = vtf_file.with_suffix('.png').name
            print(f"  -> Saved: {output_name}")
            converted += 1
        else:
            failed += 1
    
    print("-" * 50)
    print(f"Conversion complete!")
    print(f"  Converted: {converted}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    print("VTF to PNG Converter")
    print("=" * 50)
    main()
