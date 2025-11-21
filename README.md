<img width="825" height="80" alt="Image" src="https://github.com/user-attachments/assets/7a22082f-64aa-4e91-89c4-6df19d9d00e8" />

# CS2KZ Mapping Tools

Suite of tools for Counter-Strike 2 KZ map creation and development. Built with Python and ImGui by Claude and jakke.


## Features

### Core Tools

- **Mapping Mode** - Launch Hammer Editor with latest Metamod, CS2KZ plugin, and Mapping API
- **Listen Server** - Start CS2 with Metamod and CS2KZ for map testing
- **Dedicated Server** - Launch CS2 dedicated server with automatic setup
- **Insecure Mode** - Launch CS2 in insecure mode
- **Source2Viewer** - View Source 2 assets (auto-updates to latest dev build)
- **CS2 Map Importer** - Port CS:GO maps to CS2 (automated BSP extraction, material/model porting, bundled Python)
- **Skybox Converter** - Convert Source 1 skyboxes to Source 2 format
- **Loading Screen Creator** - Add custom loading screens and map descriptions
- **Point Worldtext Generator** - Create point_worldtext PNG images
- **VTF to PNG Converter** - Mass convert VTF textures to PNG
- **Sound Manager** - Add custom sounds with loop point support (requires [.NET 8 Runtime](https://dotnet.microsoft.com/download/dotnet/8.0/runtime) for VPK sounds)

## Installation

1. Download the latest ZIP from [Releases](https://github.com/jakkekz/CS2KZ-Mapping-Tools/releases)
2. Extract to a permanent location
3. Run `CS2KZMappingTools-console.exe` or `CS2KZMappingTools.exe`

**(IF you want to run the .exe from somewhere else, make a shortcut and use that.)**

### Updating

Click the update icon in the app (top-right) to automatically download and install updates. The app will:
- Download the new version
- Backup your settings
- Replace files in-place
- Restart automatically

All shortcuts and settings are preserved.

## Configuration

Settings menu allows customization of:
- Button visibility and order
- Auto-update preferences (Metamod, CS2KZ, Source2Viewer)
- Window appearance (compact mode, opacity, always on top, theme)

## Version Management

Automatic version management:
- [Metamod](https://www.sourcemm.net/downloads.php?branch=master&all=1) - Latest from AlliedModders
- [CS2KZ Plugin](https://github.com/KZGlobalTeam/cs2kz-metamod) - Latest GitHub releases
- [CS2KZ Mapping API](https://github.com/KZGlobalTeam/cs2kz-metamod/wiki/Mapping-API) - Latest releases
- [Source2Viewer](https://s2v.app/) - Auto-updates to latest dev builds

Version info shown in button tooltips.

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest new features
- Submit pull requests

## 🙏 Credits

- CS2KZ team (zer0.k)
- Source2Viewer team
- sarim-hk and andreaskeller96 for CS2 Map Importer inspiration
- AlliedModders for Metamod:Source
