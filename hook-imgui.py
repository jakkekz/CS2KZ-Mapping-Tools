# PyInstaller hook for imgui
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

datas, binaries, hiddenimports = collect_all('imgui')

# Ensure all imgui submodules are included
hiddenimports += collect_submodules('imgui')
hiddenimports += collect_submodules('imgui.integrations')

# Add specific integrations
hiddenimports += [
    'imgui.core',
    'imgui.internal', 
    'imgui.integrations.glfw',
]
