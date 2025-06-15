from .file_system_manager import FileSystemManagerAPI
from .download_endpoints import FileSystemDownloadAPI
from .google_drive_handler import GoogleDriveDownloaderAPI 
from .huggingface_handler import HuggingFaceDownloadAPI

# Register the API endpoint
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# Web extension registration
WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
