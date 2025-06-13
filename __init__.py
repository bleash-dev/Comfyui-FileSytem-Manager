from .file_system_manager import FileSystemManagerAPI
from .download_endpoints import FileSystemDownloadAPI
# Ensure google_drive_handler is loaded if it registers routes or needs initialization,
# but in this case, its API and store are used by file_system_manager.py directly.
from .google_drive_handler import GoogleDriveDownloaderAPI 

# Register the API endpoint
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

# Web extension registration
WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
