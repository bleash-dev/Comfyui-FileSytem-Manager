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

# Import the new global models manager
try:
    from .global_models_manager import GlobalModelsManager, global_models_progress_store
    global_models_manager = GlobalModelsManager()
except ImportError:
    print("Global models manager not available")
    global_models_manager = None

# Global progress tracking for downloads
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
            
            # Check if path is allowed - but for global directories, we need special handling
            is_local_path_allowed = self.is_path_allowed(target_path)
            path_exists_locally = target_path.exists()

            # Get local contents
            contents = []
            local_items = {}
            
            if path_exists_locally and is_local_path_allowed:
                for item in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    try:
                        # Handle symbolic links specially
                        if item.is_symlink():
                            # Check if the symlink target exists
                            try:
                                # Resolve the symlink to its actual target
                                actual_target = item.resolve()
                                if actual_target.exists():
                                    # Use the target's stats
                                    item_stat = actual_target.stat()
                                    symlink_target_exists = True
                                    print(f"🔗 Valid symlink: {item} -> {actual_target}")
                                else:
                                    print(f"💥 Broken symlink detected: {item} -> {actual_target}")
                                    # Remove broken symlink immediately
                                    item.unlink()
                                    print(f"🗑️ Removed broken symlink: {item}")
                                    continue
                            except (OSError, FileNotFoundError) as symlink_error:
                                print(f"💥 Broken symlink detected: {item} - {symlink_error}")
                                # Remove broken symlink immediately
                                try:
                                    item.unlink()
                                    print(f"🗑️ Removed broken symlink: {item}")
                                except:
                                    print(f"❌ Failed to remove broken symlink: {item}")
                                continue
                        else:
                            # Check if the item still exists (handle race conditions for regular files/dirs)
                            if not item.exists():
                                print(f"⚠️ Skipping non-existent item: {item}")
                                continue
                            
                            # Get item stats safely for regular files/dirs
                            try:
                                item_stat = item.stat()
                                symlink_target_exists = False  # Not a symlink
                            except (OSError, FileNotFoundError) as stat_error:
                                print(f"⚠️ Error getting stats for {item}: {stat_error}")
                                continue
                        
                        # Construct the item path consistently - always include the root directory key
                        item_relative_path = item.relative_to(self.allowed_directories[root_dir])
                        item_display_path = f"{root_dir}/{item_relative_path}".replace("\\", "/")

                        # Determine item type - treat working symlinks as their target type
                        if item.is_symlink() and symlink_target_exists:
                            # For symlinks, determine type based on the resolved target
                            item_type = 'directory' if actual_target.is_dir() else 'file'
                            item_size = item_stat.st_size if actual_target.is_file() else None
                        else:
                            # Regular files and directories
                            item_type = 'directory' if item.is_dir() else 'file'
                            item_size = item_stat.st_size if item.is_file() else None

                        item_data = {
                            'name': item.name,
                            'path': item_display_path,
                            'type': item_type,
                            'size': item_size,
                            'modified': item_stat.st_mtime,
                            'local_exists': True,
                            'global_exists': False,
                            'downloadable': False
                        }
                        
                        contents.append(item_data)
                        local_items[item.name] = item_data
                        
                    except Exception as e_item:
                        print(f"⚠️ Error processing item {item}: {e_item}")
                        # Skip problematic items instead of failing the entire operation
            
            # Add global models if we're in the models directory
            if root_dir == 'models' and global_models_manager:
                try:
                    # Get global models structure
                    global_structure = await global_models_manager.get_global_models_structure()
                    
                    # Navigate through the global structure based on the current path
                    current_global_structure = global_structure
                    
                    # If we're deeper than just "models", navigate to the correct level
                    if len(path_parts) > 1:
                        for part in path_parts[1:]:
                            if isinstance(current_global_structure, dict) and part in current_global_structure:
                                current_global_structure = current_global_structure[part]
                            else:
                                # Path doesn't exist in global structure
                                current_global_structure = {}
                                break
                    
                    # If we have a valid global structure at this level
                    if isinstance(current_global_structure, dict):
                        for item_name, item_data in current_global_structure.items():
                            # Skip empty or invalid item names - be more strict
                            if not item_name or not item_name.strip() or item_name == '':
                                print(f"Skipping invalid global model item: '{item_name}'")
                                continue
                                
                            # Construct the full path for this item
                            current_item_path = "/".join(path_parts + [item_name])
                            
                            if isinstance(item_data, dict):
                                # Check if it's a file or a category/subdirectory
                                if item_data.get('type') == 'file':
                                    # Additional validation for files
                                    s3_path = item_data.get('s3_path', '')
                                    if not s3_path or not s3_path.strip():
                                        print(f"Skipping global model with invalid s3_path: {item_name}")
                                        continue
                                        
                                    # It's a file
                                    if item_name not in local_items:
                                        # Add global model that doesn't exist locally
                                        contents.append({
                                            'name': item_name,
                                            'path': current_item_path,
                                            'type': 'file',
                                            'size': item_data.get('size', 0),
                                            'modified': None,
                                            'local_exists': False,
                                            'global_exists': True,
                                            'downloadable': True,
                                            's3_path': s3_path,
                                            'global_model_path': "/".join(path_parts[1:] + [item_name]) if len(path_parts) > 1 else item_name
                                        })
                                    else:
                                        # Mark existing local model as also available globally
                                        local_items[item_name]['global_exists'] = True
                                        local_items[item_name]['downloadable'] = False  # Already local
                                        local_items[item_name]['s3_path'] = item_data.get('s3_path', '')
                                        local_items[item_name]['global_model_path'] = "/".join(path_parts[1:] + [item_name]) if len(path_parts) > 1 else item_name
                                else:
                                    # It's a subdirectory/category
                                    if item_name not in local_items:
                                        # Add global directory that doesn't exist locally
                                        contents.append({
                                            'name': item_name,
                                            'path': current_item_path,
                                            'type': 'directory',
                                            'size': None,
                                            'modified': None,
                                            'local_exists': False,
                                            'global_exists': True,
                                            'downloadable': False
                                        })
                                    else:
                                        # Mark existing local directory as also having global content
                                        local_items[item_name]['global_exists'] = True
                            else:
                                # It's a nested structure (subdirectory)
                                if item_name not in local_items:
                                    # Add global directory that doesn't exist locally
                                    contents.append({
                                        'name': item_name,
                                        'path': current_item_path,
                                        'type': 'directory',
                                        'size': None,
                                        'modified': None,
                                        'local_exists': False,
                                        'global_exists': True,
                                        'downloadable': False
                                    })
                                else:
                                    # Mark existing local directory as also having global content
                                    local_items[item_name]['global_exists'] = True
                    
                except Exception as e:
                    print(f"Error adding global models: {e}")

            # Sort contents: directories first, then files, alphabetically
            contents.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))

            # If we have contents (either local or global), or if it's an allowed path, return success
            if contents or is_local_path_allowed or (root_dir == 'models' and global_models_manager):
                return {"success": True, "contents": contents}
            else:
                return {"success": False, "error": "Path not found or not allowed"}
            
        except Exception as e:
            print(f"Error in get_directory_contents for path '{relative_path}': {e}")
            return {"success": False, "error": str(e)}

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

            base_create_path = self.comfyui_base
            if relative_path: # If relative_path is provided, it's relative to an allowed root
                path_parts = relative_path.strip('/').split('/')
                root_dir_key = path_parts[0]
                if root_dir_key not in self.allowed_directories:
                    return {"success": False, "error": "Invalid base path for creation"}
                
                base_create_path = self.allowed_directories[root_dir_key]
                for part in path_parts[1:]:
                    base_create_path = base_create_path / part
            else: # Creating in one of the root allowed directories (e.g. "models/")
                  # This case needs careful handling or disallowing if creating directly in "models/" root is not desired.
                  # For now, let's assume relative_path will point to a subfolder like "models/loras"
                  # If relative_path is empty, it implies creating in a root like 'models', 'users'.
                  # This needs clarification. For now, let's assume it means creating in the current browsed path.
                  # If current browsed path is "models", then new folder is "models/new_folder_name".
                  # The JS client sends `this.currentPath` which can be "models" or "models/loras".
                pass # base_create_path is already comfyui_base, or should be derived from relative_path

            target_dir_path = base_create_path / directory_name
            
            if not self.is_path_allowed(target_dir_path.parent): # Check parent of the dir to be created
                 return {"success": False, "error": "Creation path not allowed"}

            if target_dir_path.exists():
                return {"success": False, "error": "Directory already exists"}
            
            target_dir_path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "message": f"Directory '{directory_name}' created successfully"}
            
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
                shutil.rmtree(item_path)
                return {"success": True, "message": f"Directory '{item_path.name}' deleted successfully"}
            else:
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

            # Validate new name (no path separators)
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

            # Create new path
            new_item_path = old_item_path.parent / new_name

            if new_item_path.exists():
                return {"success": False, "error": "Item with new name already exists"}

            if not self.is_path_allowed(new_item_path):
                return {"success": False, "error": "New path not allowed"}

            # Perform the rename
            old_item_path.rename(new_item_path)
            return {"success": True, "message": f"Item renamed to '{new_name}' successfully"}

        except Exception as e:
            print(f"Error renaming item: {e}")
            return {"success": False, "error": str(e)}

# Initialize the API
file_system_api = FileSystemManagerAPI()

# Initialize download endpoints
download_api = FileSystemDownloadAPI()

# Initialize Google Drive Handler API
google_drive_download_api = GoogleDriveDownloaderAPI()

# Initialize Hugging Face Handler API
hf_download_api = HuggingFaceDownloadAPI()

# Initialize CivitAI Handler API
civitai_download_api = CivitAIDownloadAPI()

# Initialize Direct Upload Handler API
direct_upload_api = DirectUploadAPI()

@PS.instance.routes.get("/filesystem/browse")
async def browse_directory(request):
    """API endpoint for browsing directories"""
    try:
        path = request.query.get('path', "")
        # Decode URL-encoded path components
        decoded_path = unquote(path)
        result = await file_system_api.get_directory_contents(decoded_path)
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/browse: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.post("/filesystem/create_directory")
async def create_directory(request):
    """API endpoint for creating directories"""
    try:
        data = await request.json()
        path = data.get("path", "")
        directory_name = data.get("directory_name")
        
        if not directory_name:
            return web.json_response({'success': False, 'error': 'Directory name not provided'}, status=400)
        
        decoded_path = unquote(path)
        result = file_system_api.create_directory(decoded_path, directory_name)
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/create_directory: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.delete("/filesystem/delete")
async def delete_item(request):
    """API endpoint for deleting files and directories"""
    try:
        data = await request.json()
        path = data.get("path")
        if not path:
            return web.json_response({'success': False, 'error': 'Path not provided'}, status=400)
        
        decoded_path = unquote(path)
        result = file_system_api.delete_item(decoded_path)
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/delete: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/file_info")
async def get_file_info(request):
    """API endpoint for getting file information"""
    try:
        path = request.query.get('path', '')
        result = file_system_api.get_file_info(path)
        return web.json_response(result)
    except Exception as e:
        return web.json_response(
            {"success": False, "error": str(e)}, 
            status=500
        )

@PS.instance.routes.post("/filesystem/rename_item")
async def rename_item_endpoint(request):
    """API endpoint for renaming files and directories"""
    try:
        data = await request.json()
        old_path = data.get("old_path")
        new_name = data.get("new_name")

        if not old_path or not new_name:
            return web.json_response({'success': False, 'error': 'Missing old_path or new_name'}, status=400)
        
        decoded_old_path = unquote(old_path)
        # new_name should not be URL encoded as it's a single name component
        
        result = file_system_api.rename_item(decoded_old_path, new_name)
        return web.json_response(result)
    except Exception as e:
        print(f"Error in /filesystem/rename_item: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)
        

@PS.instance.routes.get("/filesystem/download_file")
async def download_file_endpoint(request):
    """API endpoint for downloading a single file"""
    return await download_api.download_file(request)

@PS.instance.routes.post("/filesystem/download_multiple")
async def download_multiple_files_endpoint(request):
    """API endpoint for downloading multiple files as a zip archive"""
    return await download_api.download_multiple_files(request)

@PS.instance.routes.post("/filesystem/upload_from_google_drive")
async def upload_from_google_drive_endpoint(request):
    """API endpoint for uploading files from Google Drive"""
    try:
        data = await request.json()
        google_drive_url = data.get('google_drive_url')
        filename = data.get('filename')
        # model_type = data.get('model_type') # This was from the old GDrive downloader
        target_path_relative = data.get('path') # This is the FSM relative path
        overwrite = data.get('overwrite', False)
        auto_extract_zip = data.get('auto_extract_zip', True)
        session_id = data.get('session_id')
        extension = data.get('extension') # Added for GDrive uploads via FSM

        if not all([google_drive_url, filename, extension, target_path_relative is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing required fields for Google Drive upload.'}, status=400)

        # Construct the full filename with extension
        full_filename = f"{filename}.{extension}"

        # The `target_path_relative` from FSM is like "models/loras" or "users/my_folder"
        # We need to resolve this to an absolute path for GoogleDriveDownloaderAPI
        # GoogleDriveDownloaderAPI's get_download_path expects a model_type or custom_path.
        # We can treat the FSM path as a custom_path for GDrive downloader.
        
        path_parts = target_path_relative.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for Google Drive upload.'}, status=400)

        # Resolve FSM relative path to absolute path
        absolute_target_dir = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]:
            absolute_target_dir = absolute_target_dir / part
        
        if not file_system_api.is_path_allowed(absolute_target_dir) or not absolute_target_dir.is_dir():
            return web.json_response({'success': False, 'error': 'Target directory for Google Drive upload is not valid or not allowed.'}, status=400)

        # Use "custom" model_type and provide the absolute_target_dir as custom_path
        # The GoogleDriveDownloaderAPI will append the filename to this path.
        # So, custom_path should be the directory where the file will be saved.
        result = await google_drive_download_api.download_file_async(
            google_drive_url=google_drive_url,
            filename=full_filename, # Pass full filename with extension
            model_type="custom", # Use "custom" as we provide the full path
            custom_path=str(absolute_target_dir), # Pass the absolute directory path
            overwrite=overwrite,
            auto_extract_zip=auto_extract_zip,
            session_id=session_id
        )
        return web.json_response(result)
        
    except Exception as e:
        print(f"Error in /filesystem/upload_from_google_drive: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)
        

@PS.instance.routes.get("/filesystem/google_drive_progress/{session_id}")
async def get_google_drive_progress_endpoint(request):
    """API endpoint to get Google Drive download progress"""
    try:
        session_id = request.match_info['session_id']
        progress = gdrive_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e:
        return web.json_response(
            {"status": "error", "message": str(e), "percentage": 0},
            status=500
        )

@PS.instance.routes.post("/filesystem/download_from_huggingface")
async def download_from_huggingface_endpoint(request):
    """API endpoint for downloading files/repos from Hugging Face"""
    try:
        data = await request.json()
        hf_url = data.get('hf_url') # Can be repo_id or full URL to repo/file
        target_fsm_path = data.get('path') # FSM relative path
        overwrite = data.get('overwrite', False)
        session_id = data.get('session_id')
        user_token = data.get('user_token') # New: user-provided HF token

        if not all([hf_url, target_fsm_path is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing required fields for Hugging Face download.'}, status=400)

        # Resolve FSM relative path to an absolute path that hf_download_api can use
        path_parts = target_fsm_path.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for Hugging Face download.'}, status=400)
        
        # Construct absolute path to check if it's a directory and allowed
        abs_target_dir_check = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]:
            abs_target_dir_check = abs_target_dir_check / part
        
        if not file_system_api.is_path_allowed(abs_target_dir_check): # Check if the base path is allowed
             return web.json_response({'success': False, 'error': 'Target directory for Hugging Face download is not allowed.'}, status=400)
        
        # If abs_target_dir_check exists, it must be a directory
        if abs_target_dir_check.exists() and not abs_target_dir_check.is_dir():
            return web.json_response({'success': False, 'error': 'Target path for Hugging Face download exists and is not a directory.'}, status=400)

        result = await hf_download_api.download_from_huggingface(
            hf_url=hf_url,
            target_fsm_path=target_fsm_path,
            overwrite=overwrite,
            session_id=session_id,
            user_token=user_token  # Pass user token if provided
        )
        return web.json_response(result)
        
    except Exception as e:
        print(f"Error in /filesystem/download_from_huggingface: {e}")
        # Ensure session progress reflects the error
        session_id = data.get('session_id') if 'data' in locals() and isinstance(data, dict) else None
        if session_id:
            hf_progress_store[session_id] = {"status": "error", "message": str(e), "percentage": 0}
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/huggingface_progress/{session_id}")
async def get_huggingface_progress_endpoint(request):
    """API endpoint to get Hugging Face download progress"""
    try:
        session_id = request.match_info['session_id']
        progress = hf_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e:
        return web.json_response(
            {"status": "error", "message": str(e), "percentage": 0},
            status=500
        )

@PS.instance.routes.post("/filesystem/download_from_civitai")
async def download_from_civitai_endpoint(request):
    """API endpoint for downloading models from CivitAI"""
    try:
        data = await request.json()
        civitai_url = data.get('civitai_url')
        target_fsm_path = data.get('path')
        filename = data.get('filename')
        overwrite = data.get('overwrite', False)
        session_id = data.get('session_id')
        user_token = data.get('user_token')

        if not all([civitai_url, target_fsm_path is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing required fields for CivitAI download.'}, status=400)

        # Resolve FSM relative path to check if it's valid
        path_parts = target_fsm_path.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for CivitAI download.'}, status=400)
        
        # Construct absolute path to check if it's a directory and allowed
        abs_target_dir_check = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]:
            abs_target_dir_check = abs_target_dir_check / part
        
        if not file_system_api.is_path_allowed(abs_target_dir_check):
             return web.json_response({'success': False, 'error': 'Target directory for CivitAI download is not allowed.'}, status=400)
        
        # If abs_target_dir_check exists, it must be a directory
        if abs_target_dir_check.exists() and not abs_target_dir_check.is_dir():
            return web.json_response({'success': False, 'error': 'Target path for CivitAI download exists and is not a directory.'}, status=400)

        result = await civitai_download_api.download_from_civitai(
            civitai_url=civitai_url,
            target_fsm_path=target_fsm_path,
            filename=filename,
            overwrite=overwrite,
            session_id=session_id,
            user_token=user_token
        )
        return web.json_response(result)
        
    except Exception as e:
        print(f"Error in /filesystem/download_from_civitai: {e}")
        # Ensure session progress reflects the error
        session_id = data.get('session_id') if 'data' in locals() and isinstance(data, dict) else None
        if session_id:
            civitai_progress_store[session_id] = {"status": "error", "message": str(e), "percentage": 0}
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/civitai_progress/{session_id}")
async def get_civitai_progress_endpoint(request):
    """API endpoint to get CivitAI download progress"""
    try:
        session_id = request.match_info['session_id']
        progress = civitai_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e:
        return web.json_response(
            {"status": "error", "message": str(e), "percentage": 0},
            status=500
        )

# Global cancellation tracking
download_cancellation_flags = {}

@PS.instance.routes.post("/filesystem/cancel_download")
async def cancel_download_endpoint(request):
    """API endpoint for cancelling downloads"""
    try:
        data = await request.json()
        session_id = data.get('session_id')
        download_type = data.get('download_type')
        
        if not session_id:
            return web.json_response({'success': False, 'error': 'Session ID not provided'}, status=400)
        
        # Set cancellation flag based on download type
        if download_type == 'google-drive':
            download_cancellation_flags[session_id] = True
            gdrive_progress_store[session_id] = {
                "status": "cancelled",
                "message": "Download cancelled by user",
                "percentage": 0
            }
        elif download_type == 'huggingface':
            download_cancellation_flags[session_id] = True
            hf_progress_store[session_id] = {
                "status": "cancelled", 
                "message": "Download cancelled by user",
                "percentage": 0
            }
        elif download_type == 'civitai':
            download_cancellation_flags[session_id] = True
            civitai_progress_store[session_id] = {
                "status": "cancelled",
                "message": "Download cancelled by user", 
                "percentage": 0
            }
        elif download_type == 'direct-link':
            # Use the direct upload specific cancellation flags
            direct_upload_cancellation_flags[session_id] = True
            direct_upload_progress_store[session_id] = {
                "status": "cancelled",
                "message": "Download cancelled by user",
                "percentage": 0
            }
        else:
            # Fallback - set flags in all stores
            download_cancellation_flags[session_id] = True
            direct_upload_cancellation_flags[session_id] = True
        
        print(f"🚫 Download cancellation requested for session: {session_id} (type: {download_type})")
        
        return web.json_response({'success': True, 'message': 'Cancellation requested'})
        
    except Exception as e:
        print(f"Error in /filesystem/cancel_download: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.post("/filesystem/upload_from_direct_url")
async def upload_from_direct_url_endpoint(request):
    """API endpoint for uploading files from direct URLs"""
    try:
        data = await request.json()
        direct_url = data.get('direct_url')
        target_fsm_path = data.get('path')
        filename = data.get('filename')
        overwrite = data.get('overwrite', False)
        session_id = data.get('session_id')

        if not all([direct_url, target_fsm_path is not None, session_id]):
            return web.json_response({'success': False, 'error': 'Missing required fields for direct URL upload.'}, status=400)

        # Resolve FSM relative path to check if it's valid
        path_parts = target_fsm_path.strip('/').split('/')
        if not path_parts or path_parts[0] not in file_system_api.allowed_directories:
             return web.json_response({'success': False, 'error': 'Invalid target path for direct URL upload.'}, status=400)
        
        # Construct absolute path to check if it's a directory and allowed
        abs_target_dir_check = file_system_api.allowed_directories[path_parts[0]]
        for part in path_parts[1:]:
            abs_target_dir_check = abs_target_dir_check / part
        
        if not file_system_api.is_path_allowed(abs_target_dir_check):
             return web.json_response({'success': False, 'error': 'Target directory for direct URL upload is not allowed.'}, status=400)
        
        # If abs_target_dir_check exists, it must be a directory
        if abs_target_dir_check.exists() and not abs_target_dir_check.is_dir():
            return web.json_response({'success': False, 'error': 'Target path for direct URL upload exists and is not a directory.'}, status=400)

        result = await direct_upload_api.upload_from_direct_url(
            url=direct_url,
            target_fsm_path=target_fsm_path,
            filename=filename,
            overwrite=overwrite,
            session_id=session_id
        )
        return web.json_response(result)
        
    except Exception as e:
        print(f"Error in /filesystem/upload_from_direct_url: {e}")
        # Ensure session progress reflects the error
        session_id = data.get('session_id') if 'data' in locals() and isinstance(data, dict) else None
        if session_id:
            direct_upload_progress_store[session_id] = {"status": "error", "message": str(e), "percentage": 0}
        return web.json_response({'success': False, 'error': str(e)}, status=500)

@PS.instance.routes.get("/filesystem/direct_upload_progress/{session_id}")
async def get_direct_upload_progress_endpoint(request):
    """API endpoint to get direct upload progress"""
    try:
        session_id = request.match_info['session_id']
        progress = direct_upload_progress_store.get(session_id, {"status": "not_found", "message": "Session not found", "percentage": 0})
        return web.json_response(progress)
    except Exception as e:
        return web.json_response(
            {"status": "error", "message": str(e), "percentage": 0},
            status=500
        )

# Add new endpoints for global models management

@PS.instance.routes.get("/filesystem/global_models_structure")
async def get_global_models_structure(request):
    try:
        if not global_models_manager:
            return web.json_response({
                "success": False,
                "error": "Global models manager not available"
            }, status=500)
            
        force_refresh = request.query.get('force_refresh', 'false').lower() == 'true'
        structure = await global_models_manager.get_global_models_structure(force_refresh)
        
        return web.json_response({
            "success": True,
            "structure": structure
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/download_global_model")
async def download_global_model_endpoint(request):
    """API endpoint for downloading global models"""
    try:
        if not global_models_manager:
            return web.json_response({
                "success": False,
                "error": "Global models manager not available"
            }, status=500)
            
        data = await request.json()
        model_path = data.get('model_path')
        
        if not model_path:
            return web.json_response({
                "success": False,
                "error": "Model path is required"
            }, status=400)
        
        print(f"Starting download for model: {model_path}")
        
        # Start download in background
        try:
            success = await global_models_manager.download_model(model_path)
            
            return web.json_response({
                "success": success,
                "message": f"Download {'completed' if success else 'failed'} for {model_path}",
                "model_path": model_path
            })
        except Exception as download_error:
            print(f"Error in download_model: {download_error}")
            # Update progress store with error
            global_models_progress_store[model_path] = {
                "progress": 0,
                "status": "failed", 
                "error": str(download_error)
            }
            return web.json_response({
                "success": False,
                "error": f"Download failed: {str(download_error)}",
                "model_path": model_path
            })
        
    except Exception as e:
        print(f"Error in download_global_model_endpoint: {e}")
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.get("/filesystem/download_progress")
async def get_download_progress(request):
    try:
        return web.json_response({
            "success": True,
            "progress": download_progress
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.get("/filesystem/global_model_download_progress")
async def get_global_model_download_progress(request):
    """Get the current progress of global model downloads"""
    try:
        if not global_models_manager:
            return web.json_response({
                "success": False,
                "error": "Global models manager not available"
            }, status=500)
        
        return web.json_response({
            "success": True,
            "progress": global_models_progress_store
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/sync_new_model")
async def sync_new_model(request):
    """Sync a newly downloaded model to global shared storage"""
    try:
        if not global_models_manager:
            return web.json_response({
                "success": False,
                "error": "Global models manager not available"
            }, status=500)
            
        data = await request.json()
        model_path = data.get('model_path')
        
        if not model_path:
            return web.json_response({
                "success": False,
                "error": "Model path is required"
            }, status=400)
        
        success = await global_models_manager.sync_new_model_to_global(model_path)
        
        return web.json_response({
            "success": success,
            "message": f"Model {'synced' if success else 'failed to sync'} to global storage"
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

@PS.instance.routes.post("/filesystem/cancel_global_model_download")
async def cancel_global_model_download(request):
    """Cancel an ongoing global model download"""
    try:
        if not global_models_manager:
            return web.json_response({
                "success": False,
                "error": "Global models manager not available"
            }, status=500)
            
        data = await request.json()
        model_path = data.get('model_path')
        
        if not model_path:
            return web.json_response({
                "success": False,
                "error": "Model path is required"
            }, status=400)
        
        # If we have a progress entry for this model, mark it as cancelled
        if model_path in global_models_progress_store:
            global_models_progress_store[model_path]['status'] = 'cancelled'
            global_models_progress_store[model_path]['message'] = 'Download cancelled by user'
            
        return web.json_response({
            "success": True,
            "message": f"Download of {model_path} cancelled"
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)

def update_download_progress(model_path, current, total):
    """Update download progress for a model"""
    if total and total > 0:
        percentage = (current / total) * 100
    else:
        # For cases where we don't know total size, use file size as indicator
        percentage = min(100, (current / (1024 * 1024 * 100)) * 100)  # Assume 100MB as rough estimate
    
    download_progress[model_path] = {
        "current": current,
        "total": total,
        "percentage": percentage,
        "status": "downloading" if percentage < 100 else "completed"
    }
    """Update download progress for a model"""
    if total and total > 0:
        percentage = (current / total) * 100
    else:
        # For cases where we don't know total size, use file size as indicator
        percentage = min(100, (current / (1024 * 1024 * 100)) * 100)  # Assume 100MB as rough estimate
    
    download_progress[model_path] = {
        "current": current,
        "total": total,
        "percentage": percentage,
        "status": "downloading" if percentage < 100 else "completed"
    }
