import os
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from .utils import CivitAIUtils
from .progress import ProgressTracker
from ..shared_state import download_cancellation_flags

# Import model config integration
try:
    from ..model_config_integration import model_config_manager
    MODEL_CONFIG_AVAILABLE = True
except ImportError:
    print("Model config integration not available")
    MODEL_CONFIG_AVAILABLE = False

class CivitAIDownloader:
    def __init__(self):
        self.utils = CivitAIUtils()
        self.api_base = "https://civitai.com/api/v1"

    async def get_model_info(self, model_id: str, token: str = None) -> dict:
        """Get model information from CivitAI API"""
        url = f"{self.api_base}/models/{model_id}"
        
        # Add token as query parameter if provided
        if token:
            url += f"?token={token}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise ValueError(f"Model {model_id} not found on CivitAI")
                elif response.status == 401:
                    raise ValueError("Invalid CivitAI API token")
                elif response.status == 403:
                    raise ValueError("Access denied - model may be restricted or require NSFW access")
                elif response.status != 200:
                    raise ValueError(f"CivitAI API error: {response.status}")
                
                return await response.json()

    async def get_version_info(self, version_id: str, token: str = None) -> dict:
        """Get specific version information from CivitAI API"""
        url = f"{self.api_base}/model-versions/{version_id}"
        
        # Add token as query parameter if provided
        if token:
            url += f"?token={token}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise ValueError(f"Version {version_id} not found on CivitAI")
                elif response.status == 401:
                    raise ValueError("Invalid CivitAI API token")
                elif response.status == 403:
                    raise ValueError("Access denied - version may be restricted")
                elif response.status != 200:
                    raise ValueError(f"CivitAI API error: {response.status}")
                
                return await response.json()

    def select_best_file(self, files: list) -> dict:
        """Select the best file from available options"""
        if not files:
            raise ValueError("No files available for download")
        
        # Prioritize by type: Model > VAE > Config
        file_priorities = {
            'Model': 3,
            'VAE': 2,
            'Config': 1,
            'Pruned Model': 3,  # Same as Model
            'Training Data': 0  # Lowest priority
        }
        
        # Sort by priority (highest first), then by size (largest first)
        sorted_files = sorted(
            files,
            key=lambda f: (
                file_priorities.get(f.get('type', ''), 0),
                f.get('sizeKB', 0)
            ),
            reverse=True
        )
        
        return sorted_files[0]

    async def download_with_progress(self, download_url: str, target_path: str, filename: str, 
                                   session_id: str = None, token: str = None, progress_callback=None):
        """Download file with real-time progress tracking and optional progress callback"""
        # Add token as query parameter to download URL if provided
        final_download_url = download_url
        if token:
            # Check if URL already has query parameters
            separator = "&" if "?" in download_url else "?"
            final_download_url = f"{download_url}{separator}token={token}"
        
        timeout = aiohttp.ClientTimeout(total=3600, connect=30)  # 1 hour total, 30s connect
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Check for cancellation before starting request
            if session_id and download_cancellation_flags.get(session_id):
                raise asyncio.CancelledError("Download cancelled by user")
                
            async with session.get(final_download_url) as response:
                if response.status == 401:
                    raise ValueError("Invalid CivitAI API token or authentication required")
                elif response.status == 403:
                    raise ValueError("Access denied - file may be restricted or require NSFW access")
                elif response.status == 404:
                    raise ValueError("File not found on CivitAI")
                elif response.status != 200:
                    raise ValueError(f"Download failed: HTTP {response.status}")
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                ProgressTracker.update_progress(
                    session_id,
                    f"Starting download of {filename}...",
                    75
                )
                
                # Call external progress callback if provided
                if progress_callback:
                    progress_callback(session_id, f"Starting download of {filename}...", 75)
                
                async with aiofiles.open(target_path, 'wb') as file:
                    chunk_size = 1024 * 1024  # 1MB chunks for better performance
                    
                    async for chunk in response.content.iter_chunked(chunk_size):
                        # Check for cancellation on each chunk
                        if session_id and download_cancellation_flags.get(session_id):
                            # Clean up partial file
                            try:
                                await file.close()
                                Path(target_path).unlink(missing_ok=True)
                            except:
                                pass
                            raise asyncio.CancelledError("Download cancelled by user")
                        
                        await file.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percentage = 75 + int((downloaded / total_size) * 20)  # Progress from 75% to 95%
                            downloaded_formatted = self.utils.format_file_size(downloaded)
                            total_formatted = self.utils.format_file_size(total_size)
                            message = f"Downloading {filename}: {downloaded_formatted}/{total_formatted}"
                        else:
                            percentage = 85  # Fixed progress when size unknown
                            downloaded_formatted = self.utils.format_file_size(downloaded)
                            message = f"Downloading {filename}: {downloaded_formatted} (size unknown)"
                        
                        ProgressTracker.update_progress(session_id, message, percentage)
                        
                        # Call external progress callback if provided
                        if progress_callback:
                            progress_callback(session_id, message, percentage)
                
                return downloaded

    async def download_model_async(self, model_id: str, version_id: str = None, 
                                 target_fsm_path: str = None, filename: str = None,
                                 token: str = None, session_id: str = None, direct_download_url: str = None,
                                 progress_callback=None):
        """Download a model from CivitAI with progress tracking and optional progress callback"""

        try:
            # Handle direct download URLs
            if direct_download_url:
                # Check for cancellation at the start
                if session_id and download_cancellation_flags.get(session_id):
                    ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                    
                ProgressTracker.update_progress(session_id, "Using direct download URL...", 10)
                
                # Extract filename from URL or use provided filename
                if not filename:
                    # Try to get filename from URL parameters or use a default
                    url_parts = direct_download_url.split('/')
                    if 'models' in url_parts:
                        model_version_id = url_parts[url_parts.index('models') + 1].split('?')[0]
                        filename = f"civitai_model_{model_version_id}"
                    else:
                        filename = "civitai_model_download"
                
                # Determine target path
                if target_fsm_path:
                    target_dir = self.utils.get_target_path(target_fsm_path)
                else:
                    # Default to models/checkpoints for direct downloads
                    target_dir = Path(self.utils.comfyui_base) / "models" / "checkpoints"
                    target_dir.mkdir(parents=True, exist_ok=True)
                
                # Add appropriate extension if not present
                if not Path(filename).suffix:
                    filename += ".safetensors"  # Default extension for CivitAI models
                
                final_filename = self.utils.get_safe_filename(filename)
                final_path = target_dir / final_filename
                
                # Check for cancellation before file operations
                if session_id and download_cancellation_flags.get(session_id):
                    ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                
                # Check if file already exists
                if final_path.exists():
                    ProgressTracker.set_completed(
                        session_id,
                        f"File already exists: {final_filename}"
                    )
                    return {
                        "success": True,
                        "message": f"File already exists: {final_filename}",
                        "path": str(final_path)
                    }
                
                # Create temporary file for download
                temp_path = self.utils.create_temp_file(final_filename)
                
                try:
                    ProgressTracker.update_progress(
                        session_id,
                        f"Starting direct download...",
                        30
                    )
                    
                    # Call external progress callback if provided
                    if progress_callback:
                        progress_callback(session_id, f"Starting direct download...", 30)
                    
                    # Download with progress using the direct URL
                    downloaded_size = await self.download_with_progress(
                        download_url=direct_download_url,
                        target_path=temp_path,
                        filename=final_filename,
                        session_id=session_id,
                        token=token,
                        progress_callback=progress_callback
                    )
                    
                    # Check for cancellation after download
                    if session_id and download_cancellation_flags.get(session_id):
                        # Clean up temp file
                        self.utils.cleanup_temp_file(temp_path)
                        ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                        return {"success": False, "error": "Download cancelled by user"}
                    
                    ProgressTracker.update_progress(
                        session_id,
                        f"Download completed, moving to final location...",
                        95
                    )
                    
                    # Move from temp to final location
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    Path(temp_path).rename(final_path)
                    
                    # Register the model with the configuration manager
                    if MODEL_CONFIG_AVAILABLE:
                        try:
                            # Extract model info for registration
                            model_config_manager.register_civitai_model(
                                local_path=str(final_path),
                                model_id=model_id,
                                version_id=version_id,
                                direct_url=direct_download_url if direct_download_url else None
                            )
                            print(f"📝 Model registered in config: {final_path}")
                        except Exception as e:
                            print(f"⚠️ Failed to register model in config: {e}")
                    
                    success_message = f"Downloaded {final_filename} ({self.utils.format_file_size(downloaded_size)})"
                    ProgressTracker.set_completed(session_id, success_message)
                    
                    return {
                        "success": True,
                        "message": success_message,
                        "path": str(final_path),
                        "file_size": downloaded_size
                    }
                    
                except asyncio.CancelledError:
                    # Handle cancellation during download
                    self.utils.cleanup_temp_file(temp_path)
                    ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                except Exception as download_error:
                    # Clean up temp file on error
                    self.utils.cleanup_temp_file(temp_path)
                    raise download_error
            
            # Original model/version-based download logic with cancellation checks
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
                
            ProgressTracker.update_progress(session_id, "Fetching model information...", 5)
            
            # Call external progress callback if provided
            if progress_callback:
                progress_callback(session_id, "Fetching model information...", 5)
            
            # Get model information
            model_info = await self.get_model_info(model_id, token)
            
            # Check for cancellation after API call
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
                
            model_name = model_info.get('name', f'Model_{model_id}')
            model_type = model_info.get('type', 'Checkpoint')
            
            ProgressTracker.update_progress(
                session_id,
                f"Model: {model_name} (Type: {model_type})",
                10
            )
            
            # Select version
            if version_id:
                # Check for cancellation before version API call
                if session_id and download_cancellation_flags.get(session_id):
                    ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                    
                # Get specific version
                ProgressTracker.update_progress(session_id, f"Fetching version {version_id} info...", 15)
                version_info = await self.get_version_info(version_id, token)
            else:
                # Use latest version
                versions = model_info.get('modelVersions', [])
                if not versions:
                    raise ValueError("No versions available for this model")
                version_info = versions[0]  # First version is usually the latest
                version_id = str(version_info.get('id'))
            
            # Check for cancellation after version selection
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            version_name = version_info.get('name', f'Version_{version_id}')
            ProgressTracker.update_progress(
                session_id,
                f"Using version: {version_name}",
                20
            )
            
            # Select best file
            files = version_info.get('files', [])
            if not files:
                raise ValueError(f"No files available for version {version_id}")
            
            selected_file = self.select_best_file(files)
            file_name = selected_file.get('name', f'{model_name}_{version_name}')
            file_size = selected_file.get('sizeKB', 0) * 1024  # Convert KB to bytes
            download_url = selected_file.get('downloadUrl')
            
            if not download_url:
                raise ValueError("No download URL found for selected file")
            
            ProgressTracker.update_progress(
                session_id,
                f"Selected file: {file_name} ({self.utils.format_file_size(file_size)})",
                25
            )
            
            # Check for cancellation before file operations
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            # Determine target path
            if target_fsm_path:
                target_dir = self.utils.get_target_path(target_fsm_path)
            else:
                # Auto-determine based on model type
                comfyui_model_type = self.utils.determine_model_type_from_metadata(model_info)
                target_dir = Path(self.utils.comfyui_base) / "models" / comfyui_model_type
                target_dir.mkdir(parents=True, exist_ok=True)
            
            # Use provided filename or generate safe one
            if filename:
                final_filename = self.utils.get_safe_filename(filename)
                # Ensure it has the right extension
                original_ext = Path(file_name).suffix
                if not final_filename.endswith(original_ext):
                    final_filename += original_ext
            else:
                final_filename = self.utils.get_safe_filename(file_name)
            
            final_path = target_dir / final_filename
            
            # Check if file already exists
            if final_path.exists():
                ProgressTracker.set_completed(
                    session_id,
                    f"File already exists: {final_filename}"
                )
                return {
                    "success": True,
                    "message": f"File already exists: {final_filename}",
                    "path": str(final_path),
                    "model_name": model_name,
                    "version_name": version_name
                }
            
            # Create temporary file for download
            temp_path = self.utils.create_temp_file(final_filename)
            
            try:
                ProgressTracker.update_progress(
                    session_id,
                    f"Starting download from CivitAI...",
                    30
                )
                
                # Call external progress callback if provided
                if progress_callback:
                    progress_callback(session_id, f"Starting download from CivitAI...", 30)
                
                # Download with progress
                downloaded_size = await self.download_with_progress(
                    download_url=download_url,
                    target_path=temp_path,
                    filename=final_filename,
                    session_id=session_id,
                    token=token,
                    progress_callback=progress_callback
                )
                
                # Check for cancellation after download
                if session_id and download_cancellation_flags.get(session_id):
                    # Clean up temp file
                    self.utils.cleanup_temp_file(temp_path)
                    ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                
                ProgressTracker.update_progress(
                    session_id,
                    f"Download completed, moving to final location...",
                    95
                )
                
                # Move from temp to final location
                final_path.parent.mkdir(parents=True, exist_ok=True)
                Path(temp_path).rename(final_path)
                
                success_message = f"Downloaded {final_filename} ({self.utils.format_file_size(downloaded_size)})"
                ProgressTracker.set_completed(session_id, success_message)
                
                return {
                    "success": True,
                    "message": success_message,
                    "path": str(final_path),
                    "model_name": model_name,
                    "version_name": version_name,
                    "file_size": downloaded_size
                }
                
            except asyncio.CancelledError:
                # Handle cancellation during download
                self.utils.cleanup_temp_file(temp_path)
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            except Exception as download_error:
                # Clean up temp file on error
                self.utils.cleanup_temp_file(temp_path)
                raise download_error
                
        except asyncio.CancelledError:
            # Handle cancellation at any level
            ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
            return {"success": False, "error": "Download cancelled by user"}
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "Access denied" in error_msg or "authentication required" in error_msg:
                ProgressTracker.set_access_restricted(
                    session_id,
                    "We are unable to download this model because access is restricted by the owner. If you need it ASAP you can input your own CivitAI API token below. We will download it on your behalf. Make sure you have access to the model before proceeding.<br><br>Note that we don't store your CivitAI token on our servers."
                )
                return {
                    "success": False,
                    "error": "Access restricted - CivitAI API token required for private/restricted models",
                    "error_type": "access_restricted"
                }
            else:
                ProgressTracker.set_error(session_id, error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
        finally:
            # Clean up cancellation flag
            if session_id and session_id in download_cancellation_flags:
                del download_cancellation_flags[session_id]
