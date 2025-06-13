import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any
import folder_paths
import server

# Import download endpoints
from .download_endpoints import FileSystemDownloadAPI
# Import Google Drive Handler
from .google_drive_handler import GoogleDriveDownloaderAPI, progress_store as gdrive_progress_store


class FileSystemManagerAPI:
    def __init__(self):
        self.comfyui_base = Path(folder_paths.base_path)
        # Define allowed directories for security
        self.allowed_directories = {
            'models': self.comfyui_base / 'models',
            'users': self.comfyui_base / 'users', 
            'custom_nodes': self.comfyui_base / 'custom_nodes'
        }
        
        # Ensure base directories exist
        for dir_path in self.allowed_directories.values():
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def is_path_allowed(self, path: Path) -> bool:
        """Check if the path is within allowed directories"""
        try:
            path = path.resolve()
            for allowed_dir in self.allowed_directories.values():
                if path.is_relative_to(allowed_dir.resolve()):
                    return True
            return False
        except Exception:
            return False
    
    def get_directory_contents(self, relative_path: str = "") -> Dict[str, Any]:
        """Get contents of a directory"""
        try:
            if not relative_path:
                # Return root directories
                return {
                    "success": True,
                    "path": "",
                    "contents": [
                        {
                            "name": name,
                            "type": "directory",
                            "path": name,
                            "size": None,
                            "modified": None
                        }
                        for name in self.allowed_directories.keys()
                    ]
                }
            
            # Parse the path
            path_parts = relative_path.strip('/').split('/')
            root_dir = path_parts[0]
            
            if root_dir not in self.allowed_directories:
                return {"success": False, "error": "Directory not allowed"}
            
            target_path = self.allowed_directories[root_dir]
            if len(path_parts) > 1:
                target_path = target_path / '/'.join(path_parts[1:])
            
            if not self.is_path_allowed(target_path) or not target_path.exists():
                return {"success": False, "error": "Directory not found or not allowed"}
            
            contents = []
            try:
                for item in sorted(target_path.iterdir()):
                    if item.name.startswith('.'):
                        continue  # Skip hidden files
                    
                    item_info = {
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "path": str(Path(relative_path) / item.name),
                        "size": item.stat().st_size if item.is_file() else None,
                        "modified": item.stat().st_mtime
                    }
                    contents.append(item_info)
            except PermissionError:
                return {"success": False, "error": "Permission denied"}
            
            return {
                "success": True,
                "path": relative_path,
                "contents": contents
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_directory(self, relative_path: str, directory_name: str) -> Dict[str, Any]:
        """Create a new directory"""
        try:
            # Validate directory name
            if not directory_name or '/' in directory_name or '\\' in directory_name:
                return {"success": False, "error": "Invalid directory name"}
            
            if not relative_path:
                return {"success": False, "error": "Cannot create directory at root level"}
            
            path_parts = relative_path.strip('/').split('/')
            root_dir = path_parts[0]
            
            if root_dir not in self.allowed_directories:
                return {"success": False, "error": "Directory not allowed"}
            
            target_path = self.allowed_directories[root_dir]
            if len(path_parts) > 1:
                target_path = target_path / '/'.join(path_parts[1:])
            
            new_dir_path = target_path / directory_name
            
            if not self.is_path_allowed(new_dir_path):
                return {"success": False, "error": "Path not allowed"}
            
            if new_dir_path.exists():
                return {"success": False, "error": "Directory already exists"}
            
            new_dir_path.mkdir(parents=True)
            
            return {
                "success": True,
                "message": f"Directory '{directory_name}' created successfully",
                "path": str(Path(relative_path) / directory_name)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_item(self, relative_path: str) -> Dict[str, Any]:
        """Delete a file or directory"""
        try:
            if not relative_path:
                return {"success": False, "error": "Cannot delete root directories"}
            
            path_parts = relative_path.strip('/').split('/')
            root_dir = path_parts[0]
            
            if root_dir not in self.allowed_directories:
                return {"success": False, "error": "Directory not allowed"}
            
            target_path = self.allowed_directories[root_dir]
            if len(path_parts) > 1:
                target_path = target_path / '/'.join(path_parts[1:])
            else:
                return {"success": False, "error": "Cannot delete root directories"}
            
            if not self.is_path_allowed(target_path) or not target_path.exists():
                return {"success": False, "error": "Item not found or not allowed"}
            
            if target_path.is_dir():
                shutil.rmtree(target_path)
                message = f"Directory '{target_path.name}' deleted successfully"
            else:
                target_path.unlink()
                message = f"File '{target_path.name}' deleted successfully"
            
            return {"success": True, "message": message}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_file_info(self, relative_path: str) -> Dict[str, Any]:
        """Get detailed information about a file"""
        try:
            if not relative_path:
                return {"success": False, "error": "No file specified"}
            
            path_parts = relative_path.strip('/').split('/')
            root_dir = path_parts[0]
            
            if root_dir not in self.allowed_directories:
                return {"success": False, "error": "Directory not allowed"}
            
            target_path = self.allowed_directories[root_dir]
            if len(path_parts) > 1:
                target_path = target_path / '/'.join(path_parts[1:])
            
            if not self.is_path_allowed(target_path) or not target_path.exists():
                return {"success": False, "error": "File not found or not allowed"}
            
            if target_path.is_dir():
                return {"success": False, "error": "Path is a directory, not a file"}
            
            stat = target_path.stat()
            
            return {
                "success": True,
                "name": target_path.name,
                "path": relative_path,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "extension": target_path.suffix.lower(),
                "absolute_path": str(target_path)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# Initialize the API
file_system_api = FileSystemManagerAPI()

# Initialize download endpoints
download_api = FileSystemDownloadAPI()

# Initialize Google Drive Handler API
google_drive_download_api = GoogleDriveDownloaderAPI()

@server.PromptServer.instance.routes.get("/filesystem/browse")
async def browse_directory(request):
    """API endpoint for browsing directories"""
    try:
        path = request.query.get('path', '')
        result = file_system_api.get_directory_contents(path)
        return server.web.json_response(result)
    except Exception as e:
        return server.web.json_response(
            {"success": False, "error": str(e)}, 
            status=500
        )

@server.PromptServer.instance.routes.post("/filesystem/create_directory")
async def create_directory(request):
    """API endpoint for creating directories"""
    try:
        data = await request.json()
        path = data.get('path', '')
        directory_name = data.get('directory_name', '')
        
        result = file_system_api.create_directory(path, directory_name)
        return server.web.json_response(result)
    except Exception as e:
        return server.web.json_response(
            {"success": False, "error": str(e)}, 
            status=500
        )

@server.PromptServer.instance.routes.delete("/filesystem/delete")
async def delete_item(request):
    """API endpoint for deleting files and directories"""
    try:
        data = await request.json()
        path = data.get('path', '')
        
        result = file_system_api.delete_item(path)
        return server.web.json_response(result)
    except Exception as e:
        return server.web.json_response(
            {"success": False, "error": str(e)}, 
            status=500
        )

@server.PromptServer.instance.routes.get("/filesystem/file_info")
async def get_file_info(request):
    """API endpoint for getting file information"""
    try:
        path = request.query.get('path', '')
        result = file_system_api.get_file_info(path)
        return server.web.json_response(result)
    except Exception as e:
        return server.web.json_response(
            {"success": False, "error": str(e)}, 
            status=500
        )

@server.PromptServer.instance.routes.get("/filesystem/download_file")
async def download_file_endpoint(request):
    """API endpoint for downloading a single file"""
    return await download_api.download_file(request)

@server.PromptServer.instance.routes.post("/filesystem/download_multiple")
async def download_multiple_files_endpoint(request):
    """API endpoint for downloading multiple files as a zip archive"""
    return await download_api.download_multiple_files(request)

@server.PromptServer.instance.routes.post("/filesystem/upload_from_google_drive")
async def upload_from_google_drive_endpoint(request):
    """API endpoint for uploading files from Google Drive"""
    try:
        data = await request.json()
        session_id = data.get('session_id') # For progress tracking

        required_fields = ['google_drive_url', 'filename', 'extension', 'path']
        for field in required_fields:
            if field not in data or not data[field]:
                return server.web.json_response(
                    {"success": False, "error": f"Missing or empty required field: {field}"},
                    status=400
                )
        
        # The 'path' from frontend is the relative directory within ComfyUI (e.g., "models/checkpoints")
        upload_destination_path = data['path']
        
        # Validate that the upload_destination_path is allowed by checking against FSM's logic if needed,
        # though typically the frontend only allows navigating allowed paths.
        # For simplicity, we trust the 'path' provided by the FSM frontend is valid.
        # The GoogleDriveHandlerAPI.get_target_download_path will construct the full absolute path.

        result = await google_drive_download_api.download_file_async(
            google_drive_url=data['google_drive_url'],
            filename_no_ext=data['filename'],
            extension=data['extension'],
            upload_destination_path_str=upload_destination_path,
            overwrite=data.get('overwrite', False),
            auto_extract_zip=data.get('auto_extract_zip', True),
            session_id=session_id
            # progress_callback can be added if server-side logging of progress is needed beyond client polling
        )
        
        # No explicit cleanup of gdrive_progress_store here, download_file_async handles its lifecycle.
        return server.web.json_response(result)
        
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in /filesystem/upload_from_google_drive: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return server.web.json_response(
            {"success": False, "error": f"An unexpected error occurred: {str(e)}"},
            status=500
        )

@server.PromptServer.instance.routes.get("/filesystem/google_drive_progress/{session_id}")
async def get_google_drive_progress_endpoint(request):
    """API endpoint to get Google Drive download progress"""
    try:
        session_id = request.match_info['session_id']
        progress = gdrive_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return server.web.json_response(progress)
    except Exception as e:
        return server.web.json_response(
            {"status": "error", "message": str(e), "percentage": 0},
            status=500
        )
