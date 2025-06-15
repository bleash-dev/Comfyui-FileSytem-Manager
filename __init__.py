# ComfyUI FileSystem Manager Extension
# Provides file system management capabilities for ComfyUI
# 
# Features:
# - Browse files and directories
# - Create, rename, delete files and folders  
# - Upload from Google Drive, Hugging Face, CivitAI, and Direct URLs
# - Download files with progress tracking
# - Real-time progress updates and cancellation support

from .file_system_manager import *
from .google_drive_handler import *
from .huggingface_handler import *
from .civitai_handler import *
from .direct_upload_handler import *
from .download_endpoints import *

# Register the API endpoint
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# Web extension registration
WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']

__version__ = "1.0.0"
__author__ = "FileSystem Manager Team"
__description__ = "Comprehensive file system management for ComfyUI with multiple upload sources"
