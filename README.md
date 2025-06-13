# ComfyUI File System Manager

A ComfyUI web extension that adds a file system management interface directly to the ComfyUI header, allowing users to browse, manage, and organize files and folders within ComfyUI's core directories.

## Features

- **Header Icon Integration**: Folder icon in ComfyUI header for easy access
- **Directory Browsing**: Navigate through models/, users/, and custom_nodes/ directories
- **File Management**: Create new folders, delete files and directories
- **Safety Controls**: Restricted access to only allowed directories for security
- **Responsive UI**: Clean modal interface with breadcrumb navigation
- **File Information**: View file sizes, modification dates, and types
- **Multi-selection**: Select multiple items for batch operations
- **Keyboard Support**: Enter to create folders, Escape to cancel

## Installation

### Manual Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/YOUR_USERNAME/ComfyUI-FileSystem-Manager.git
# Restart ComfyUI
```

## Usage

1. **Click the folder icon** in the ComfyUI header (top toolbar)
2. **Browse directories**: Click on folders to navigate into them
3. **Create folders**: Click "New Folder" button and enter folder name
4. **Delete items**: Select files/folders and click "Delete" button
5. **Navigation**: Use breadcrumb navigation to go back to parent directories

### Available Directories

- **models/**: All model files (checkpoints, VAE, LoRA, etc.)
- **users/**: User-specific data and configurations
- **custom_nodes/**: Custom node extensions and plugins

### Interface Features

- **Breadcrumb Navigation**: Shows current path and allows quick navigation
- **File Table**: Displays name, type, size, and modification date
- **Action Buttons**: New Folder, Delete, Refresh
- **Multi-selection**: Ctrl/Cmd+click to select multiple items
- **Status Bar**: Shows current operation status and item count

## Security

- Access is restricted to only the models/, users/, and custom_nodes/ directories
- Cannot navigate outside of allowed directories
- Cannot delete root directories (models, users, custom_nodes)
- Hidden files (starting with .) are not displayed

## Requirements

- ComfyUI
- Python 3.8+

## License

MIT License
