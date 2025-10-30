# CS2KZ Mapping Tools

A comprehensive suite of tools for Counter-Strike 2 KZ (Kreedz) map creation and development. Built with Python and ImGui for a clean, intuitive interface.

Polished, beautifully crafted ✨ through relentless, high-volume iteration and trial-and-error 💥. The underlying code often reflects this rapid process, utilizing dense, unconventional, yet highly functional logic 🧠 reminiscent of machine-generated efficiency 🤖.


## 🎯 Features

### Core Tools

- **🗺️ Mapping Mode**  
  Launch CS2 Hammer Editor with the latest Metamod, CS2KZ plugin, and Mapping API versions pre-configured

- **🎮 Listen Server**  
  Start CS2 with the latest Metamod and CS2KZ plugin for testing your maps

- **🖥️ Dedicated Server**  
  Launch a CS2 Dedicated Server with automatic Metamod and CS2KZ setup

- **🔓 Insecure Mode**  
  Launch CS2 in insecure mode

### Additional Tools

- **👁️ Source2Viewer**  
  View and inspect Source 2 assets with automatic updates to the latest dev build

- **🔄 CS2 Map Importer**  
  Port CS:GO maps to CS2 format  
  *Inspired by sarim-hk and andreaskeller96*

- **🌅 Skybox Converter**  
  Convert Source 1 cubemap skyboxes to CS2-compatible format

- **🖼️ Loading Screen Creator**  
  Add custom loading screen images, map icons, and descriptions to your maps

- **📝 Point Worldtext Generator**  
  Create CS:GO style point_worldtext PNG images

- **🎨 VTF to PNG Converter**  
  Convert CS:GO VTF texture files to PNG images

## 🚀 Getting Started

### Prerequisites

- Windows OS
- Counter-Strike 2 installed

### Installation (Standalone Executable)

1. Download the latest `CS2KZMappingTools.exe` from the [Releases](https://github.com/jakkekz/CS2KZ-Mapping-Tools/releases) page
2. Run `CS2KZMappingTools.exe`


## ⚙️ Configuration

The application automatically:
- Downloads and installs the latest Metamod versions
- Updates CS2KZ plugin to the latest release
- Configures CS2 for optimal mapping workflow
- Caches downloaded components in `%TEMP%\.CS2KZ-mapping-tools`

### Settings

Access settings via the menu to customize:
- Button visibility and order
- Auto-update preferences (Metamod, CS2KZ, Source2Viewer)
- Window appearance (compact mode, opacity, always on top)
- Theme (dark/light mode)

## 📦 Version Management

The tools automatically manage versions:
- **Metamod**: Fetched from AlliedModders
- **CS2KZ Plugin**: Latest releases from GitHub
- **CS2KZ Mapping API**: Latest releases from GitHub
- **Source2Viewer**: Auto-updates via development builds

Version information is displayed in button tooltips.

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
