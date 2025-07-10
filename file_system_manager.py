import os
import subprocess
import json
import tempfile
import shutil
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import unquote
import folder_paths
from server import PromptServer as PS
from aiohttp import web
from .routes.missing_models_routes import setup_missing_models_routes

# Import the new global models manager
try:
    from .global_models_manager import GlobalModelsManager, global_models_progress_store
    global_models_manager = GlobalModelsManager()
except ImportError:
    print("Global models manager not available")
    global_models_manager = None
    global_models_progress_store = {} # Define it even if manager fails to import, for safety

# Global progress tracking for downloads (This seems like a general one, maybe for non-global downloads?)
# If it's redundant with global_models_progress_store or other specific stores, consider consolidating.
download_progress = {} 

# Import download endpoints
from .download_endpoints import FileSystemDownloadAPI
from .google_drive_handler import GoogleDriveDownloaderAPI, progress_store as gdrive_progress_store
# Import Hugging Face Handler
from .huggingface_handler import HuggingFaceDownloadAPI, hf_progress_store
# Import CivitAI Handler
from .civitai_handler import CivitAIDownloadAPI, civitai_progress_store

# Import Direct Upload Handler
from .direct_upload_handler import DirectUploadAPI, direct_upload_progress_store, direct_upload_cancellation_flags

# Import Sync Manager Integration
try:
    from .sync_manager_integration import sync_manager_api
    SYNC_MANAGER_AVAILABLE = True
except ImportError:
    print("Sync manager integration not available")
    sync_manager_api = None
    SYNC_MANAGER_AVAILABLE = False

# Import Workflow Execution API
try:
    from .workflow_execution_api import workflow_execution_api
    WORKFLOW_EXECUTION_AVAILABLE = True
except ImportError:
    print("Workflow execution API not available")
    workflow_execution_api = None
    WORKFLOW_EXECUTION_AVAILABLE = False

# Import workflow monitor to register its endpoints
try:
    from .workflow_monitor import workflow_monitor
    print("Workflow monitor endpoints registered")
except ImportError:
    print("Workflow monitor not available")
    workflow_monitor = None


class FileSystemManagerAPI:
    def __init__(self):
        """Initialize the file system manager with allowed directories."""
        self.comfyui_base = Path(folder_paths.base_path)
        
        # Define allowed directories for security
        self.allowed_directories = {
            'models': self.comfyui_base / 'models',
            'user': self.comfyui_base / 'user', 
            'input': self.comfyui_base / 'input',
            'output': self.comfyui_base / 'output',
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
                if path.is_relative_to(allowed_dir.resolve()): # Updated to use is_relative_to
                    return True
            return False
        except Exception:
            return False
    
    async def get_directory_contents(self, relative_path: str = "") -> Dict[str, Any]:
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

            # Append the rest of the path
            for part in path_parts[1:]:
                target_path = target_path / part
            
            is_local_path_allowed = self.is_path_allowed(target_path)
            path_exists_locally = target_path.exists()

            contents = []
            local_items = {}
            
            if path_exists_locally and is_local_path_allowed:
                for item in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    try:
                        actual_target = None # Initialize actual_target
                        symlink_target_exists = False # Initialize
                        if item.is_symlink():
                            try:
                                actual_target = item.resolve()
                                if actual_target.exists():
                                    item_stat = actual_target.stat()
                                    symlink_target_exists = True
                                else:
                                    item.unlink()
                                    continue
                            except (OSError, FileNotFoundError):
                                try:
                                    item.unlink()
                                except: pass # Ignore error if unlinking fails
                                continue
                        else:
                            if not item.exists():
                                continue
                            try:
                                item_stat = item.stat()
                            except (OSError, FileNotFoundError):
                                continue
                        
                        item_relative_path = item.relative_to(self.allowed_directories[root_dir])
                        item_display_path = f"{root_dir}/{item_relative_path}".replace("\\", "/")

                        if item.is_symlink() and symlink_target_exists and actual_target: # Check actual_target is not None
                            item_type = 'directory' if actual_target.is_dir() else 'file'
                            item_size = item_stat.st_size if actual_target.is_file() else None
                        else:
                            item_type = 'directory' if item.is_dir() else 'file'
                            item_size = item_stat.st_size if item.is_file() else None

                        item_data = {
                            'name': item.name, 'path': item_display_path, 'type': item_type,
                            'size': item_size, 'modified': item_stat.st_mtime,
                            'local_exists': True, 'global_exists': False, 'downloadable': False
                        }
                        contents.append(item_data)
                        local_items[item.name] = item_data
                    except Exception as e_item:
                        print(f"⚠️ Error processing item {item}: {e_item}")
            
            if root_dir == 'models' and global_models_manager:
                try:
                    global_structure = await global_models_manager.get_global_models_structure()
                    current_global_structure = global_structure
                    
                    if len(path_parts) > 1:
                        for part in path_parts[1:]:
                            current_global_structure = current_global_structure.get(part, {}) if isinstance(current_global_structure, dict) else {}
                    
                    if isinstance(current_global_structure, dict):
                        for item_name, item_info in current_global_structure.items(): # Renamed item_data to item_info for clarity
                            if not item_name or not item_name.strip(): continue
                            current_item_path = "/".join(path_parts + [item_name])
                            
                            global_model_item_path_for_frontend = "/".join(path_parts[1:] + [item_name]) if len(path_parts) > 1 else item_name

                            if isinstance(item_info, dict): # Check if item_info is a dict (could be file or sub-category)
                                if item_info.get('type') == 'file': # Explicitly a file from global store
                                    s3_path = item_info.get('s3_path', '')
                                    if not s3_path or not s3_path.strip(): continue
                                    
                                    if item_name not in local_items:
                                        contents.append({
                                            'name': item_name, 'path': current_item_path, 'type': 'file',
                                            'size': item_info.get('size', 0), 'modified': None,
                                            'local_exists': False, 'global_exists': True, 'downloadable': True,
                                            's3_path': s3_path, 'global_model_path': global_model_item_path_for_frontend
                                        })
                                    else: # Local item exists, mark it as global
                                        local_items[item_name]['global_exists'] = True
                                        local_items[item_name]['downloadable'] = False # Already local
                                        local_items[item_name]['s3_path'] = s3_path
                                        local_items[item_name]['global_model_path'] = global_model_item_path_for_frontend
                                else: # Could be a category (directory-like) within global store, not a direct file
                                    if item_name not in local_items:
                                        contents.append({
                                            'name': item_name, 'path': current_item_path, 'type': 'directory',
                                            'size': None, 'modified': None,
                                            'local_exists': False, 'global_exists': True, 'downloadable': False
                                        })
                                    else:
                                        local_items[item_name]['global_exists'] = True
                            # If item_info is not a dict, it implies it's a nested structure (directory)
                            # This case should be handled if item_info itself is a dict representing a folder
                            # The current logic correctly identifies it as a directory if it's a dict and not type 'file'.
                except Exception as e:
                    print(f"Error adding global models: {e}")

            contents.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))

            if contents or is_local_path_allowed or (root_dir == 'models' and global_models_manager):
                return {"success": True, "contents": contents}
            else:
                return {"success": False, "error": "Path not found or not allowed"}
        except Exception as e:
            print(f"Error in get_directory_contents for path '{relative_path}': {e}")
            return {"success": False, "error": str(e)}

    # ... (get_file_info, create_directory, delete_item, rename_item methods remain the same) ...
    def get_file_info(self, relative_path: str) -> Dict[str, Any]:
        """Get information about a specific file"""
        try:
            if not relative_path:
                return {"success": False, "error": "No path provided"}

            path_parts = relative_path.strip('/').split('/')
            root_dir_key = path_parts[0]
            if root_dir_key not in self.allowed_directories:
                return {"success": False, "error": "Invalid path"}

            item_path = self.allowed_directories[root_dir_key]
            for part in path_parts[1:]:
                item_path = item_path / part

            if not self.is_path_allowed(item_path):
                return {"success": False, "error": "Path not allowed"}

            if item_path.exists():
                stat_info = item_path.stat()
                return {
                    "success": True,
                    "name": item_path.name,
                    "path": relative_path,
                    "type": "directory" if item_path.is_dir() else "file",
                    "size": stat_info.st_size if item_path.is_file() else None,
                    "modified": stat_info.st_mtime,
                    "local_exists": True
                }
            else:
                return {"success": False, "error": "File not found"}
            
        except Exception as e:
            print(f"Error getting file info: {e}")
            return {"success": False, "error": str(e)}

    def create_directory(self, relative_path: str, directory_name: str) -> Dict[str, Any]:
        """Create a new directory"""
        try:
            if not directory_name or '/' in directory_name or '\\' in directory_name:
                return {"success": False, "error": "Invalid directory name"}

            base_create_path = self.comfyui_base # Default to base if relative_path is empty
            
            if relative_path: 
                path_parts = relative_path.strip('/').split('/')
                root_dir_key = path_parts[0]
                if root_dir_key not in self.allowed_directories:
                    return {"success": False, "error": "Invalid base path for creation"}
                
                # Start from the allowed root, then append sub-parts of relative_path
                base_create_path = self.allowed_directories[root_dir_key]
                for part in path_parts[1:]: # Skip the root_dir_key itself
                    base_create_path = base_create_path / part
            else: # No relative_path given, means we are creating in a root dir like "models", "users"
                  # The directory_name itself will be the new root-level folder.
                  # This path needs to be chosen carefully. For now, assume this means creating in one of the allowed roots.
                  # Let's assume directory_name will be one of the keys in self.allowed_directories
                  # Or it's a new directory *inside* one of them.
                  # The client sends currentPath. If currentPath is "", it means user is at FSM root.
                  # If currentPath is "models", it means "models/new_folder_name".
                  # This logic relies on `relative_path` being correctly formed by the client.
                  # If relative_path is "models", new dir is "models/directory_name"
                  # If relative_path is "", new dir is "directory_name" inside ComfyUI base (this needs to be restricted)

                  # Correct logic: if relative_path is empty, it means FSM root.
                  # We should not allow creating arbitrary folders at ComfyUI base.
                  # The creation should happen *within* one of the allowed_directories.
                  # So, if relative_path is empty, client must select a root first.
                  # If relative_path is "models", target is "models/directory_name".
                if not relative_path: # Disallow creation at true ComfyUI root from FSM root view
                     return {"success": False, "error": "Cannot create directory at the ComfyUI root. Select a base folder like 'models' or 'input' first."}
                # If relative_path points to an allowed root key (e.g. "models"), then base_create_path is already set.

            target_dir_path = base_create_path / directory_name
            
            # Check if the PARENT of the target_dir_path is allowed.
            # This handles cases where base_create_path itself might be deep.
            if not self.is_path_allowed(target_dir_path.parent):
                 return {"success": False, "error": "Creation path not allowed"}

            if target_dir_path.exists():
                return {"success": False, "error": "Directory already exists"}
            
            target_dir_path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "message": f"Directory '{directory_name}' created successfully in '{relative_path}'"}
            
        except Exception as e:
            print(f"Error creating directory: {e}")
            return {"success": False, "error": str(e)}

    def delete_item(self, relative_path: str) -> Dict[str, Any]:
        """Delete a file or directory"""
        try:
            if not relative_path:
                return {"success": False, "error": "No path provided for deletion"}

            path_parts = relative_path.strip('/').split('/')
            root_dir_key = path_parts[0]
            if root_dir_key not in self.allowed_directories:
                return {"success": False, "error": "Invalid path for deletion"}

            item_path = self.allowed_directories[root_dir_key]
            for part in path_parts[1:]:
                item_path = item_path / part

            if not self.is_path_allowed(item_path) or not item_path.exists():
                return {"success": False, "error": "Item not found or not allowed"}

            if item_path.is_dir():
                shutil.rmtree(item_path) # Recursively delete directory
                return {"success": True, "message": f"Directory '{item_path.name}' deleted successfully"}
            else: # It's a file
                item_path.unlink()
                return {"success": True, "message": f"File '{item_path.name}' deleted successfully"}
            
        except Exception as e:
            print(f"Error deleting item: {e}")
            return {"success": False, "error": str(e)}

    def rename_item(self, old_relative_path: str, new_name: str) -> Dict[str, Any]:
        """Rename a file or directory"""
        try:
            if not old_relative_path or not new_name:
                return {"success": False, "error": "Missing old path or new name"}

            if '/' in new_name or '\\' in new_name:
                return {"success": False, "error": "New name cannot contain path separators"}

            path_parts = old_relative_path.strip('/').split('/')
            root_dir_key = path_parts[0]
            if root_dir_key not in self.allowed_directories:
                return {"success": False, "error": "Invalid path for renaming"}

            old_item_path = self.allowed_directories[root_dir_key]
            for part in path_parts[1:]:
                old_item_path = old_item_path / part

            if not self.is_path_allowed(old_item_path) or not old_item_path.exists():
                return {"success": False, "error": "Item not found or not allowed"}

            new_item_path = old_item_path.parent / new_name

            if new_item_path.exists():
                return {"success": False, "error": "Item with new name already exists"}

            if not self.is_path_allowed(new_item_path): # Check if the new path is also allowed
                return {"success": False, "error": "New path location is not allowed"}

            old_item_path.rename(new_item_path)
            return {"success": True, "message": f"Item renamed to '{new_name}' successfully"}

        except Exception as e:
            print(f"Error renaming item: {e}")
            return {"success": False, "error": str(e)}


# Initialize the API
file_system_api = FileSystemManagerAPI()
download_api = FileSystemDownloadAPI()
google_drive_download_api = GoogleDriveDownloaderAPI()
hf_download_api = HuggingFaceDownloadAPI()
civitai_download_api = CivitAIDownloadAPI()
direct_upload_api = DirectUploadAPI()

# --- API Endpoints ---

@PS.instance.routes.get("/filesystem/browse")
async def browse_directory_endpoint(request): # Renamed to avoid conflict
    try:
        path = request.query.get('path', "")
        decoded_path = unquote(path)
        result = await file_system_api.get_directory_contents(decoded_path)
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/browse: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.post("/filesystem/create_directory")
async def create_directory_endpoint(request): # Renamed
    try:
        data = await request.json()
        path = data.get("path", "")
        directory_name = data.get("directory_name")
        if not directory_name: return web.json_response({'success': False, 'error': 'Directory name missing'}, status=400)
        result = file_system_api.create_directory(unquote(path), directory_name)
        return web.json_response(result)
    except Exception as e: return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.delete("/filesystem/delete")
async def delete_item_endpoint(request): # Renamed
    try:
        data = await request.json()
        path = data.get("path")
        if not path: return web.json_response({'success': False, 'error': 'Path not provided'}, status=400)
        result = file_system_api.delete_item(unquote(path))
        return web.json_response(result)
    except Exception as e: return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/file_info")
async def get_file_info_endpoint(request): # Renamed
    try:
        path = request.query.get('path', '')
        result = file_system_api.get_file_info(unquote(path)) # unquote path here too
        return web.json_response(result)
    except Exception as e: return web.json_response({"success": False, "error": str(e)}, status=500)

@PS.instance.routes.post("/filesystem/rename_item")
async def rename_item_endpoint(request):
    try:
        data = await request.json()
        old_path = data.get("old_path")
        new_name = data.get("new_name")
        if not old_path or not new_name: return web.json_response({'success': False, 'error': 'Missing params'}, status=400)
        result = file_system_api.rename_item(unquote(old_path), new_name) # new_name is not a path component
        return web.json_response(result)
    except Exception as e: return web.json_response({'success': False, 'error': str(e)}, status=500)
        
@PS.instance.routes.get("/filesystem/download_file")
async def download_file_route_endpoint(request): # Renamed
    return await download_api.download_file(request)

@PS.instance.routes.post("/filesystem/download_multiple")
async def download_multiple_files_route_endpoint(request): # Renamed
    return await download_api.download_multiple_files(request)

# ... (Google Drive, Hugging Face, CivitAI, Direct Upload Endpoints - keeping them as they are) ...
@PS.instance.routes.post("/filesystem/upload_from_google_drive")
async def upload_from_google_drive_endpoint(request):
    """API endpoint for uploading files from Google Drive"""
    try:
        data = await request.json()
        google_drive_url = data.get('google_drive_url')
        filename = data.get('filename')
        target_path_relative = data.get('path') 
        overwrite = data.get('overwrite', False)
        auto_extract_zip = data.get('auto_extract_zip', True)
        session_id = data.get('session_id')
        extension = data.get('extension')

        if not all([google_drive_url, filename, extension, target_path_relative is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing required fields for GDrive upload.'}, status=400)

        full_filename = f"{filename}.{extension}"
        path_parts = target_path_relative.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for GDrive upload.'}, status=400)

        absolute_target_dir = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]:
            absolute_target_dir = absolute_target_dir / part
        
        if not file_system_api.is_path_allowed(absolute_target_dir) or (absolute_target_dir.exists() and not absolute_target_dir.is_dir()):
            return web.json_response({'success': False, 'error': 'Target directory for GDrive not valid/allowed.'}, status=400)

        result = await google_drive_download_api.download_file_async(
            google_drive_url=google_drive_url, filename=full_filename, model_type="custom",
            custom_path=str(absolute_target_dir), overwrite=overwrite,
            auto_extract_zip=auto_extract_zip, session_id=session_id
        )
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/upload_from_google_drive: {e}")
        session_id = data.get('session_id') if 'data' in locals() and isinstance(data, dict) else None # Ensure data is defined
        if session_id: gdrive_progress_store[session_id] = {"status": "error", "message": str(e), "percentage": 0}
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/google_drive_progress/{session_id}")
async def get_google_drive_progress_endpoint(request):
    try:
        session_id = request.match_info['session_id']
        progress = gdrive_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e: return web.json_response({"status": "error", "message": str(e), "percentage": 0}, status=500)

@PS.instance.routes.post("/filesystem/download_from_huggingface")
async def download_from_huggingface_endpoint(request):
    try:
        data = await request.json()
        hf_url = data.get('hf_url')
        target_fsm_path = data.get('path')
        overwrite = data.get('overwrite', False)
        session_id = data.get('session_id')
        user_token = data.get('user_token')

        if not all([hf_url, target_fsm_path is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing fields for HF download.'}, status=400)

        path_parts = target_fsm_path.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for HF download.'}, status=400)
        
        abs_target_dir_check = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]: abs_target_dir_check = abs_target_dir_check / part
        
        if not file_system_api.is_path_allowed(abs_target_dir_check) or \
           (abs_target_dir_check.exists() and not abs_target_dir_check.is_dir()):
             return web.json_response({'success': False, 'error': 'Target directory for HF not valid/allowed.'}, status=400)

        result = await hf_download_api.download_from_huggingface(
            hf_url=hf_url, target_fsm_path=target_fsm_path, overwrite=overwrite,
            session_id=session_id, user_token=user_token
        )
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/download_from_huggingface: {e}")
        session_id = data.get('session_id') if 'data' in locals() and isinstance(data, dict) else None
        if session_id: hf_progress_store[session_id] = {"status": "error", "message": str(e), "percentage": 0}
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/huggingface_progress/{session_id}")
async def get_huggingface_progress_endpoint(request):
    try:
        session_id = request.match_info['session_id']
        progress = hf_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e: return web.json_response({"status": "error", "message": str(e), "percentage": 0}, status=500)

@PS.instance.routes.post("/filesystem/download_from_civitai")
async def download_from_civitai_endpoint(request):
    try:
        data = await request.json()
        civitai_url = data.get('civitai_url')
        target_fsm_path = data.get('path')
        filename = data.get('filename')
        overwrite = data.get('overwrite', False)
        session_id = data.get('session_id')
        user_token = data.get('user_token')

        if not all([civitai_url, target_fsm_path is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing fields for CivitAI download.'}, status=400)

        path_parts = target_fsm_path.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for CivitAI.'}, status=400)
        
        abs_target_dir_check = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]: abs_target_dir_check = abs_target_dir_check / part
        
        if not file_system_api.is_path_allowed(abs_target_dir_check) or \
           (abs_target_dir_check.exists() and not abs_target_dir_check.is_dir()):
             return web.json_response({'success': False, 'error': 'Target dir for CivitAI not valid/allowed.'}, status=400)

        result = await civitai_download_api.download_from_civitai(
            civitai_url=civitai_url, target_fsm_path=target_fsm_path, filename=filename,
            overwrite=overwrite, session_id=session_id, user_token=user_token
        )
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/download_from_civitai: {e}")
        session_id = data.get('session_id') if 'data' in locals() and isinstance(data, dict) else None
        if session_id: civitai_progress_store[session_id] = {"status": "error", "message": str(e), "percentage": 0}
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/civitai_progress/{session_id}")
async def get_civitai_progress_endpoint(request):
    try:
        session_id = request.match_info['session_id']
        progress = civitai_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e: return web.json_response({"status": "error", "message": str(e), "percentage": 0}, status=500)

download_cancellation_flags = {} # General cancellation flags, might be superseded by type-specific

@PS.instance.routes.post("/filesystem/cancel_download")
async def cancel_download_endpoint(request):
    try:
        data = await request.json()
        session_id = data.get('session_id')
        download_type = data.get('download_type') # e.g., 'google-drive', 'huggingface', 'civitai', 'direct-link'

        if not session_id: return web.json_response({'success': False, 'error': 'Session ID missing'}, status=400)
        
        print(f"🚫 Download cancellation requested for session: {session_id} (type: {download_type})")
        # Use type-specific cancellation flags and progress stores
        if download_type == 'google-drive':
            # google_drive_handler should check its own cancellation mechanism if it has one
            # For now, we update its progress store directly.
            download_cancellation_flags[session_id] = True
            gdrive_progress_store[session_id] = {"status": "cancelled", "message": "User cancelled", "percentage": 0}
        elif download_type == 'huggingface':
            # hf_handler should check its own cancellation flags
            download_cancellation_flags[session_id] = True
            hf_progress_store[session_id] = {"status": "cancelled", "message": "User cancelled", "percentage": 0}
        elif download_type == 'civitai':
            # civitai_handler should check its own cancellation flags
            civitai_progress_store[session_id] = {"status": "cancelled", "message": "User cancelled", "percentage": 0}
        elif download_type == 'direct-link':
            direct_upload_cancellation_flags[session_id] = True # This flag is used by direct_upload_handler
            direct_upload_progress_store[session_id] = {"status": "cancelled", "message": "User cancelled", "percentage": 0}
        else: # Generic cancellation if type is unknown or not handled by specific flags
            download_cancellation_flags[session_id] = True
            # Also set the direct_upload_cancellation_flags as a common fallback for now
            direct_upload_cancellation_flags[session_id] = True


        return web.json_response({'success': True, 'message': 'Cancellation requested'})
    except Exception as e:
        print(f"Error in /filesystem/cancel_download: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.post("/filesystem/upload_from_direct_url")
async def upload_from_direct_url_endpoint(request):
    try:
        data = await request.json()
        direct_url = data.get('direct_url')
        target_fsm_path = data.get('path')
        filename = data.get('filename')
        overwrite = data.get('overwrite', False)
        session_id = data.get('session_id')

        if not all([direct_url, target_fsm_path is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing fields for direct URL upload.'}, status=400)

        path_parts = target_fsm_path.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for direct URL.'}, status=400)
        
        abs_target_dir_check = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]: abs_target_dir_check = abs_target_dir_check / part
        
        if not file_system_api.is_path_allowed(abs_target_dir_check) or \
           (abs_target_dir_check.exists() and not abs_target_dir_check.is_dir()):
             return web.json_response({'success': False, 'error': 'Target dir for direct URL not valid/allowed.'}, status=400)

        result = await direct_upload_api.upload_from_direct_url(
            url=direct_url, target_fsm_path=target_fsm_path, filename=filename,
            overwrite=overwrite, session_id=session_id
        )
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/upload_from_direct_url: {e}")
        session_id = data.get('session_id') if 'data' in locals() and isinstance(data, dict) else None
        if session_id: direct_upload_progress_store[session_id] = {"status": "error", "message": str(e), "percentage": 0}
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/direct_link_progress/{session_id}")
async def get_direct_upload_progress_endpoint(request):
    try:
        session_id = request.match_info['session_id']
        progress = direct_upload_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e: return web.json_response({"status": "error", "message": str(e), "percentage": 0}, status=500)

# --- Global Models Management Endpoints ---

@PS.instance.routes.get("/filesystem/global_models_structure")
async def get_global_models_structure_endpoint(request): # Renamed
    try:
        if not global_models_manager: return web.json_response({"success": False, "error": "Global models disabled"}, status=500)
        force_refresh = request.query.get('force_refresh', 'false').lower() == 'true'
        structure = await global_models_manager.get_global_models_structure(force_refresh)
        return web.json_response({"success": True, "structure": structure})
    except Exception as e: return web.json_response({"success": False, "error": str(e)}, status=500)

@PS.instance.routes.post("/filesystem/download_global_model")
async def download_global_model_route_endpoint(request): # Renamed
    try:
        if not global_models_manager: return web.json_response({"success": False, "error": "Global models disabled"}, status=500)
        data = await request.json()
        model_path = data.get('model_path')
        if not model_path: return web.json_response({"success": False, "error": "Model path required"}, status=400)
        
        print(f"Received request to download global model: {model_path}")
        # This now correctly calls the async method in GlobalModelsManager
        # The download_model method itself handles background tasking and progress updates.
        # We just need to initiate it and respond quickly.
        asyncio.create_task(global_models_manager.download_model(model_path)) # Start download in background

        return web.json_response({
            "success": True,
            "message": f"Download initiated for {model_path}. Check progress.",
            "model_path": model_path
        })
    except Exception as e:
        print(f"Error initiating global model download: {e}")
        model_path = data.get('model_path') # Get model_path again for error reporting
        if model_path: global_models_progress_store[model_path] = {"progress": 0, "status": "failed", "error": str(e)}
        return web.json_response({"success": False, "error": str(e)}, status=500)

@PS.instance.routes.get("/filesystem/download_progress") # This seems like a general progress endpoint
async def get_download_progress_endpoint(request): # Renamed
    try:
        # This 'download_progress' dict seems generic. If it's for global models,
        # it should probably use global_models_progress_store instead or be clearly defined.
        return web.json_response({"success": True, "progress": download_progress})
    except Exception as e: return web.json_response({"success": False, "error": str(e)}, status=500)

@PS.instance.routes.get("/filesystem/global_model_download_progress")
async def get_global_model_download_progress_endpoint(request): # Renamed
    try:
        if not global_models_manager: return web.json_response({"success": False, "error": "Global models disabled"}, status=500)
        return web.json_response({"success": True, "progress": global_models_progress_store})
    except Exception as e: return web.json_response({"success": False, "error": str(e)}, status=500)

@PS.instance.routes.post("/filesystem/sync_new_model")
async def sync_new_model_endpoint(request): # Renamed
    try:
        if not global_models_manager: return web.json_response({"success": False, "error": "Global models disabled"}, status=500)
        data = await request.json()
        model_path = data.get('model_path')
        if not model_path: return web.json_response({"success": False, "error": "Model path required"}, status=400)
        success = await global_models_manager.sync_new_model_to_global(model_path)
        return web.json_response({"success": success, "message": f"Sync status: {success}"})
    except Exception as e: return web.json_response({"success": False, "error": str(e)}, status=500)

@PS.instance.routes.post("/filesystem/cancel_global_model_download")
async def cancel_global_model_download_endpoint(request): # Renamed
    try:
        if not global_models_manager: return web.json_response({"success": False, "error": "Global models disabled"}, status=500)
        data = await request.json()
        model_path = data.get('model_path')
        if not model_path: return web.json_response({"success": False, "error": "Model path required"}, status=400)
        
        # Call manager to handle cancellation logic (e.g., setting flags for its tasks)
        await global_models_manager.cancel_download(model_path)
            
        return web.json_response({"success": True, "message": f"Cancellation requested for {model_path}"})
    except Exception as e: return web.json_response({"success": False, "error": str(e)}, status=500)

# NEW ENDPOINT
@PS.instance.routes.post("/filesystem/clear_global_model_progress")
async def clear_global_model_progress_endpoint(request):
    """API endpoint to remove a specific model path from the global_models_progress_store"""
    try:
        if not global_models_manager: # Also check if the store itself exists, though it should if manager is imported
            return web.json_response({
                "success": False,
                "error": "Global models manager (and progress store) not available"
            }, status=500)
            
        data = await request.json()
        model_path = data.get('model_path')
        
        if not model_path:
            return web.json_response({
                "success": False,
                "error": "Model path is required to clear progress"
            }, status=400)
        
        # Remove the entry if it exists
        if model_path in global_models_progress_store:
            del global_models_progress_store[model_path]
            print(f"🧹 Cleared progress for global model: {model_path}")
            return web.json_response({
                "success": True,
                "message": f"Progress for model '{model_path}' cleared."
            })
        else:
            return web.json_response({
                "success": False, # Or True, depending on if "not found" is an error
                "message": f"No active progress found for model '{model_path}' to clear."
            })
            
    except Exception as e:
        print(f"Error in /filesystem/clear_global_model_progress: {e}")
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)


# This function 'update_download_progress' appears twice. Consolidating into one.
# It also seems to update a generic 'download_progress' dict, which might be different from
# global_models_progress_store. If this is intended for other types of downloads, it's fine.
# If it's meant for global models, it should update global_models_progress_store.
# For now, I'll keep one instance of it.
def update_download_progress(model_path, current, total):
    """Update download progress for a model (generic progress store)"""
    if total and total > 0:
        percentage = (current / total) * 100
    else:
        percentage = min(100, (current / (1024 * 1024 * 100)) * 100)  # Assume 100MB as rough estimate for unknown total
    
    download_progress[model_path] = {
        "current": current,
        "total": total,
        "percentage": percentage,
        "status": "downloading" if percentage < 100 else "completed"
    }

# Ensure workflow_monitor endpoints are registered if available
if workflow_monitor:
    # workflow_monitor should ideally register its own routes
    # For example, if it has a method like workflow_monitor.register_routes(PS.instance.routes)
    # This ensures encapsulation. For now, assuming it's done within its import or init.
    pass

# --- Sync Manager Endpoints ---

@PS.instance.routes.get("/filesystem/sync/status")
async def get_sync_status_endpoint(request):
    """Get current sync status"""
    if not SYNC_MANAGER_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Sync manager not available"
        }, status=503)
    
    try:
        result = sync_manager_api.get_sync_status()
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/sync/unlock")
async def force_unlock_sync_endpoint(request):
    """Force unlock sync locks"""
    if not SYNC_MANAGER_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Sync manager not available"
        }, status=503)
    
    try:
        data = await request.json()
        sync_type = data.get('sync_type')  # Optional, None means unlock all
        
        result = sync_manager_api.force_unlock_sync(sync_type)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/sync/test")
async def test_sync_lock_endpoint(request):
    """Test sync lock mechanism"""
    if not SYNC_MANAGER_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Sync manager not available"
        }, status=503)
    
    try:
        data = await request.json()
        sync_type = data.get('sync_type', 'test_sync')
        
        result = sync_manager_api.test_sync_lock(sync_type)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/sync/run")
async def run_sync_endpoint(request):
    """Run a specific sync operation"""
    if not SYNC_MANAGER_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Sync manager not available"
        }, status=503)
    
    try:
        data = await request.json()
        sync_type = data.get('sync_type')
        
        if not sync_type:
            return web.json_response({
                "success": False,
                "error": "sync_type is required"
            }, status=400)
        
        # Run sync asynchronously to avoid blocking
        result = await sync_manager_api.run_sync_async(sync_type)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/sync/run_all")
async def run_all_syncs_endpoint(request):
    """Run all sync operations"""
    if not SYNC_MANAGER_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Sync manager not available"
        }, status=503)
    
    try:
        # Run all syncs asynchronously
        result = await sync_manager_api.run_all_syncs_async()
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.get("/filesystem/sync/list")
async def list_sync_scripts_endpoint(request):
    """List available sync scripts"""
    if not SYNC_MANAGER_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Sync manager not available"
        }, status=503)
    
    try:
        result = sync_manager_api.list_sync_scripts()
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.get("/filesystem/sync/logs/{sync_type}")
async def get_sync_logs_endpoint(request):
    """Get logs for a specific sync type"""
    if not SYNC_MANAGER_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Sync manager not available"
        }, status=503)
    
    try:
        sync_type = request.match_info['sync_type']
        lines = int(request.query.get('lines', 20))
        
        result = sync_manager_api.get_sync_logs(sync_type, lines)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

# --- Workflow Execution Endpoints ---

@PS.instance.routes.post("/filesystem/workflow/execute")
async def start_workflow_execution_endpoint(request):
    """Start workflow execution"""
    if not WORKFLOW_EXECUTION_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Workflow execution API not available"
        }, status=503)
    
    try:
        data = await request.json()
        workflow_json = data.get('workflow')
        client_id = data.get('client_id')
        
        if not workflow_json:
            return web.json_response({
                "success": False,
                "error": "workflow is required"
            }, status=400)
        
        result = await workflow_execution_api.start_workflow_execution(workflow_json, client_id)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.get("/filesystem/workflow/status/{execution_id}")
async def get_workflow_execution_status_endpoint(request):
    """Get workflow execution status"""
    if not WORKFLOW_EXECUTION_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Workflow execution API not available"
        }, status=503)
    
    try:
        execution_id = request.match_info['execution_id']
        result = workflow_execution_api.get_execution_status(execution_id)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/workflow/cancel")
async def cancel_workflow_execution_endpoint(request):
    """Cancel workflow execution"""
    if not WORKFLOW_EXECUTION_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Workflow execution API not available"
        }, status=503)
    
    try:
        data = await request.json()
        execution_id = data.get('execution_id')
        
        if not execution_id:
            return web.json_response({
                "success": False,
                "error": "execution_id is required"
            }, status=400)
        
        result = workflow_execution_api.cancel_execution(execution_id)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.get("/filesystem/workflow/list")
async def list_workflow_executions_endpoint(request):
    """List recent workflow executions"""
    if not WORKFLOW_EXECUTION_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Workflow execution API not available"
        }, status=503)
    
    try:
        limit = int(request.query.get('limit', 50))
        result = workflow_execution_api.list_executions(limit)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/workflow/cleanup")
async def cleanup_workflow_executions_endpoint(request):
    """Clean up old workflow execution records"""
    if not WORKFLOW_EXECUTION_AVAILABLE:
        return web.json_response({
            "success": False,
            "error": "Workflow execution API not available"
        }, status=503)
    
    try:
        data = await request.json()
        max_age_hours = int(data.get('max_age_hours', 24))
        
        result = workflow_execution_api.cleanup_old_executions(max_age_hours)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

print("File System Manager API routes registered.")
setup_missing_models_routes(PS.instance.routes)