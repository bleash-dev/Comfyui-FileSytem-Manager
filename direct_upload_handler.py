import os
import asyncio
import aiohttp
import aiofiles
import tempfile
from pathlib import Path
from urllib.parse import urlparse
import folder_paths

# Global progress tracking for direct uploads
direct_upload_progress_store = {}

# Global cancellation tracking - defined here to avoid circular imports
direct_upload_cancellation_flags = {}

class DirectUploadProgressTracker:
    @staticmethod
    def update_progress(session_id: str, message: str, percentage: int, status: str = "progress"):
        """Update progress for a session"""
        if session_id:
            direct_upload_progress_store[session_id] = {
                "status": status, 
                "message": message, 
                "percentage": percentage
            }
            print(f"🔄 Direct Upload Progress Update - Session: {session_id}, Percentage: {percentage}%, Message: {message}")

    @staticmethod
    def set_completed(session_id: str, message: str):
        """Mark session as completed"""
        if session_id:
            direct_upload_progress_store[session_id] = {
                "status": "completed", 
                "message": message, 
                "percentage": 100
            }
            print(f"✅ Direct Upload Completed - Session: {session_id}, Message: {message}")

    @staticmethod
    def set_error(session_id: str, message: str):
        """Mark session as error"""
        if session_id:
            direct_upload_progress_store[session_id] = {
                "status": "error", 
                "message": message, 
                "percentage": 0
            }
            print(f"❌ Direct Upload Error - Session: {session_id}, Message: {message}")

    @staticmethod
    def set_cancelled(session_id: str, message: str):
        """Mark session as cancelled"""
        if session_id:
            direct_upload_progress_store[session_id] = {
                "status": "cancelled",
                "message": message, 
                "percentage": 0
            }
            print(f"🚫 Direct Upload Cancelled - Session: {session_id}, Message: {message}")

class DirectUploadUtils:
    def __init__(self):
        self.comfyui_base = folder_paths.base_path

    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable units"""
        if size_bytes == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        if unit_index == 0:  # Bytes
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"

    def get_target_path(self, fsm_relative_path: str) -> Path:
        """Resolves an FSM relative path to an absolute path."""
        path_parts = fsm_relative_path.strip('/').split('/')
        if not path_parts:
            raise ValueError("Invalid FSM relative path.")

        current_path = Path(self.comfyui_base)
        for part in path_parts:
            current_path = current_path / part
        
        current_path.mkdir(parents=True, exist_ok=True)
        return current_path

    def get_safe_filename(self, url: str, custom_filename: str = None) -> str:
        """Generate a safe filename from URL or custom name"""
        if custom_filename:
            # Clean custom filename
            safe_name = "".join(c for c in custom_filename if c.isalnum() or c in "._- ")
            safe_name = safe_name.strip()
            if not safe_name:
                safe_name = "downloaded_file"
            return safe_name
        
        # Extract filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename or '.' not in filename:
            # Generate filename from URL components
            filename = f"download_{abs(hash(url)) % 10000}"
        
        # Clean filename
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._-")
        if not safe_name:
            safe_name = "downloaded_file"
        
        return safe_name

    def create_temp_file(self, filename: str) -> str:
        """Create a temporary file path"""
        temp_dir = Path(tempfile.gettempdir())
        temp_path = temp_dir / f"direct_upload_{abs(hash(filename)) % 10000}_{filename}"
        return str(temp_path)

    def cleanup_temp_file(self, temp_path: str):
        """Clean up temporary file"""
        try:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
                print(f"🗑️ Cleaned up temp file: {temp_path}")
        except Exception as e:
            print(f"⚠️ Failed to clean up temp file {temp_path}: {e}")

class DirectUploadDownloader:
    def __init__(self):
        self.utils = DirectUploadUtils()

    async def download_with_progress(self, url: str, target_path: str, filename: str, 
                                   session_id: str = None, progress_callback=None):
        """Download file with real-time progress tracking"""
        timeout = aiohttp.ClientTimeout(total=3600, connect=30)  # 1 hour total, 30s connect
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Check for cancellation before starting request
            if session_id and direct_upload_cancellation_flags.get(session_id):
                raise asyncio.CancelledError("Download cancelled by user")
                
            async with session.get(url) as response:
                if response.status == 404:
                    raise ValueError("File not found at the provided URL")
                elif response.status == 403:
                    raise ValueError("Access forbidden - the file may be restricted")
                elif response.status != 200:
                    raise ValueError(f"Download failed: HTTP {response.status}")
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                DirectUploadProgressTracker.update_progress(
                    session_id,
                    f"Starting download of {filename}...",
                    10
                )
                
                async with aiofiles.open(target_path, 'wb') as file:
                    chunk_size = 1024 * 1024  # 1MB chunks for better performance
                    
                    async for chunk in response.content.iter_chunked(chunk_size):
                        # Check for cancellation on each chunk
                        if session_id and direct_upload_cancellation_flags.get(session_id):
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
                            percentage = 10 + int((downloaded / total_size) * 80)  # Progress from 10% to 90%
                            downloaded_formatted = self.utils.format_file_size(downloaded)
                            total_formatted = self.utils.format_file_size(total_size)
                            message = f"Downloading {filename}: {downloaded_formatted}/{total_formatted}"
                        else:
                            percentage = 50  # Fixed progress when size unknown
                            downloaded_formatted = self.utils.format_file_size(downloaded)
                            message = f"Downloading {filename}: {downloaded_formatted} (size unknown)"
                        
                        DirectUploadProgressTracker.update_progress(session_id, message, percentage)
                        
                        if progress_callback:
                            progress_callback(downloaded, total_size)
                
                return downloaded

    async def download_from_direct_url(self, url: str, target_fsm_path: str, 
                                     filename: str = None, overwrite: bool = False,
                                     session_id: str = None):
        """Download a file from a direct URL with progress tracking"""
        try:
            # Check for cancellation at the start
            if session_id and direct_upload_cancellation_flags.get(session_id):
                DirectUploadProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
                
            DirectUploadProgressTracker.update_progress(session_id, "Validating URL...", 5)
            
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError("Invalid URL provided")
            
            # Check for cancellation
            if session_id and direct_upload_cancellation_flags.get(session_id):
                DirectUploadProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            # Determine target path
            target_dir = self.utils.get_target_path(target_fsm_path)
            
            # Generate filename
            if not filename:
                filename = self.utils.get_safe_filename(url)
            else:
                filename = self.utils.get_safe_filename(url, filename)
            
            final_path = target_dir / filename
            
            # Check for cancellation before file operations
            if session_id and direct_upload_cancellation_flags.get(session_id):
                DirectUploadProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            # Check if file already exists
            if final_path.exists() and not overwrite:
                DirectUploadProgressTracker.set_completed(
                    session_id,
                    f"File already exists: {filename}"
                )
                return {
                    "success": True,
                    "message": f"File already exists: {filename}",
                    "path": str(final_path)
                }
            
            # Create temporary file for download
            temp_path = self.utils.create_temp_file(filename)
            
            try:
                DirectUploadProgressTracker.update_progress(
                    session_id,
                    f"Starting download from URL...",
                    8
                )
                
                # Download with progress
                downloaded_size = await self.download_with_progress(
                    url=url,
                    target_path=temp_path,
                    filename=filename,
                    session_id=session_id
                )
                
                # Check for cancellation after download
                if session_id and direct_upload_cancellation_flags.get(session_id):
                    # Clean up temp file
                    self.utils.cleanup_temp_file(temp_path)
                    DirectUploadProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                
                DirectUploadProgressTracker.update_progress(
                    session_id,
                    f"Download completed, moving to final location...",
                    95
                )
                
                # Move from temp to final location
                final_path.parent.mkdir(parents=True, exist_ok=True)
                if final_path.exists() and overwrite:
                    final_path.unlink()
                
                Path(temp_path).rename(final_path)
                
                success_message = f"Downloaded {filename} ({self.utils.format_file_size(downloaded_size)})"
                DirectUploadProgressTracker.set_completed(session_id, success_message)
                
                return {
                    "success": True,
                    "message": success_message,
                    "path": str(final_path),
                    "file_size": downloaded_size
                }
                
            except asyncio.CancelledError:
                # Handle cancellation during download
                self.utils.cleanup_temp_file(temp_path)
                DirectUploadProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            except Exception as download_error:
                # Clean up temp file on error
                self.utils.cleanup_temp_file(temp_path)
                raise download_error
                
        except asyncio.CancelledError:
            # Handle cancellation at any level
            DirectUploadProgressTracker.set_cancelled(session_id, "Download cancelled by user")
            return {"success": False, "error": "Download cancelled by user"}
        except Exception as e:
            error_msg = str(e)
            DirectUploadProgressTracker.set_error(session_id, error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        finally:
            # Clean up cancellation flag
            if session_id and session_id in direct_upload_cancellation_flags:
                del direct_upload_cancellation_flags[session_id]

class DirectUploadAPI:
    def __init__(self):
        self.downloader = DirectUploadDownloader()

    async def upload_from_direct_url(self, url: str, target_fsm_path: str, 
                                   filename: str = None, overwrite: bool = False,
                                   session_id: str = None):
        """Upload a file from a direct URL with progress tracking"""
        return await self.downloader.download_from_direct_url(
            url=url,
            target_fsm_path=target_fsm_path,
            filename=filename,
            overwrite=overwrite,
            session_id=session_id
        )
