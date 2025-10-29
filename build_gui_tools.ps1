# Build script for creating all GUI tool executables
# This will be run by GitHub Actions

Write-Host "Building GUI tool executables..."

# Build CS2Importer
Write-Host "Building CS2Importer.exe..."
pyinstaller --onefile --windowed `
  --name=CS2Importer `
  --icon=icons/porting.ico `
  --add-data="icons;icons" `
  --add-data="utils;utils" `
  --collect-all imgui `
  --collect-all glfw `
  --collect-all OpenGL `
  --hidden-import=vdf `
  scripts/porting/cs2importer.py

# Build SkyboxConverter
Write-Host "Building SkyboxConverter.exe..."
pyinstaller --onefile --windowed `
  --name=SkyboxConverter `
  --icon=icons/skybox.ico `
  --hidden-import=PIL.ImageTk `
  --hidden-import=PIL.ImageDraw `
  --hidden-import=numpy `
  scripts/skybox_gui.py

# Build VTF2PNG
Write-Host "Building VTF2PNG.exe..."
pyinstaller --onefile --windowed `
  --name=VTF2PNG `
  --icon=icons/vtf2png.ico `
  --hidden-import=PIL.ImageTk `
  --hidden-import=vtf2img `
  scripts/vtf2png_gui.py

# Build LoadingScreenCreator
Write-Host "Building LoadingScreenCreator.exe..."
pyinstaller --onefile --windowed `
  --name=LoadingScreenCreator `
  --icon=icons/loading.ico `
  --add-data="scripts;scripts" `
  --add-data="chars;chars" `
  --hidden-import=PIL.ImageTk `
  --hidden-import=PIL.ImageDraw `
  --hidden-import=PIL.ImageFont `
  scripts/creator_gui.py

# Build PointWorldText
Write-Host "Building PointWorldText.exe..."
pyinstaller --onefile --windowed `
  --name=PointWorldText `
  --icon=icons/text.ico `
  --hidden-import=PIL.ImageTk `
  --hidden-import=PIL.ImageDraw `
  --hidden-import=PIL.ImageFont `
  scripts/pointworldtext.py

Write-Host "All GUI tools built successfully!"
Write-Host "Executables are in dist/ folder"
