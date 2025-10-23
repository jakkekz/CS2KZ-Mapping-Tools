import time
import os
import winreg
import vdf
import subprocess
import psutil

def get_steam_directory():
    """Get the Steam installation directory from the Windows Registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            return steam_path
    except FileNotFoundError:
        print("Steam is not installed or the registry key was not found.")
        return None

def find_cs2_library_path(libraryfolders_path):
    """Parse the libraryfolders.vdf file to find CS2 library path."""
    if not os.path.exists(libraryfolders_path):
        print(f"libraryfolders.vdf not found at {libraryfolders_path}")
        return None

    with open(libraryfolders_path, 'r', encoding='utf-8') as file:
        library_data = vdf.load(file)

    if 'libraryfolders' in library_data:
        for _, folder in library_data['libraryfolders'].items():
            if 'apps' in folder and '730' in folder['apps']:
                return folder['path']
    print("Failed to find CS2 library path.")
    return None

def get_cs2_path():
    """Get the full CS2 installation path."""
    steam_path = get_steam_directory()
    if steam_path is None:
        return None
    library_path = find_cs2_library_path(os.path.join(steam_path, "steamapps", "libraryfolders.vdf"))
    if library_path is None:
        return None
    with open(os.path.join(library_path, 'steamapps', 'appmanifest_730.acf'), 'r', encoding='utf-8') as file:
        return os.path.join(library_path, 'steamapps', 'common', vdf.load(file)['AppState']['installdir'])

if __name__ == '__main__':
    path = get_cs2_path()
    if path is None:
        print('Failed to get CS2 path. Closing in 3 seconds...')
        time.sleep(3)
        exit()

    cs2_exe = os.path.join(path, 'game', 'bin', 'win64', 'cs2.exe')
    print(f"Launching CS2 insecure instance from '{cs2_exe}'...")
    process = subprocess.Popen([cs2_exe, '-insecure'])
    
    # Wait for CS2 to close
    while any(p.name() == 'cs2.exe' for p in psutil.process_iter(['name'])):
        time.sleep(1)
    
    # Clean up steam_appid.txt if it exists
    try:
        if os.path.exists('steam_appid.txt'):
            os.remove('steam_appid.txt')
    except:
        pass
    
    print('CS2 closed. Done!')
