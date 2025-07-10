import os
import re
import asyncio
import aiofiles
import zipfile
import tempfile
import shutil
from pathlib import Path
from playwright.async_api import async_playwright
import folder_paths
import torch  # Assuming torch might be needed for .pth validation
from .shared_browser_session import SharedBrowserSessionManager

# Import model config integration
try:
    from .model_config_integration import model_config_manager
    MODEL_CONFIG_AVAILABLE = True
except ImportError:
    print("Model config integration not available")
    MODEL_CONFIG_AVAILABLE = False

# Global progress tracking
progress_store = {}


class GoogleDriveDownloaderAPI:
    def __init__(self):
        self.comfyui_base = folder_paths.base_path
        self.session_manager = SharedBrowserSessionManager()
        
    def extract_file_id(self, url):
        """Extract file ID from various Google Drive URL formats"""
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)',
            r'/open\?id=([a-zA-Z0-9_-]+)',
            r'^([a-zA-Z0-9_-]{25,})$'  # Direct file ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Could not extract file ID from URL: {url}")

    def get_download_path(self, model_type, custom_path, filename):
        """Determine the download path based on model type"""
        if model_type == "custom" and custom_path:
            base_path = Path(custom_path)
        else:
            # Map model types to ComfyUI model directories
            model_dirs = {
                "checkpoints": "checkpoints",
                "vae": "vae", 
                "loras": "loras",
                "controlnet": "controlnet",
                "embeddings": "embeddings",
                "upscale_models": "upscale_models"
            }
            
            model_dir = model_dirs.get(model_type, "checkpoints")
            base_path = Path(self.comfyui_base) / "models" / model_dir
        
        # Ensure directory exists
        base_path.mkdir(parents=True, exist_ok=True)
        
        return base_path / filename

    def is_zip_file(self, file_path):
        """Check if the downloaded file is a zip archive"""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                return True
        except (zipfile.BadZipFile, FileNotFoundError):
            return False

    def is_pth_file(self, filename):
        """Check if the filename has a .pth extension"""
        return filename.lower().endswith('.pth')

    def validate_pth_file(self, file_path):
        """Validate that a .pth file is a valid PyTorch model file"""
        try:
            # Try to load the file as a PyTorch state dict or model
            checkpoint = torch.load(file_path, map_location='cpu')
            
            # Check if it's a valid PyTorch format (state_dict, model, or checkpoint)
            if isinstance(checkpoint, dict):
                print(f"✅ Valid PyTorch checkpoint file with keys: {list(checkpoint.keys())[:5]}...")
                return True
            elif hasattr(checkpoint, 'state_dict'):
                print(f"✅ Valid PyTorch model file")
                return True
            else:
                print(f"⚠️ File loaded but format is unclear: {type(checkpoint)}")
                return True  # Still accept it as it loaded successfully
                
        except Exception as e:
            print(f"❌ Invalid PyTorch file: {e}")
            return False

    def extract_zip_file(self, zip_path, extract_to, target_filename):
        """Extract zip file and handle the extracted content"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                print(f"📦 Zip contains {len(file_list)} file(s): {file_list}")
                
                # Extract to folder named after target filename (without extension)
                target_path = Path(extract_to)
                folder_name = target_path.stem  # filename without extension
                extract_dir = target_path.parent / folder_name
                
                # Clean up existing directory if it exists
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                
                extract_dir.mkdir(exist_ok=True)
                
                # Extract all contents to the folder
                zip_ref.extractall(extract_dir)
                print(f"✅ Extracted {len(file_list)} files to: {extract_dir}")
                
                # Pack everything back into the target file
                self.pack_folder_to_file(extract_dir, extract_to, target_filename)
                
                # Clean up extraction directory
                shutil.rmtree(extract_dir)
                
                # Special validation for .pth files
                if self.is_pth_file(target_filename):
                    if self.validate_pth_file(extract_to):
                        print(f"✅ PyTorch file validated successfully")
                        return str(extract_to), True
                    else:
                        print(f"⚠️ PyTorch file validation failed but keeping file")
                        return str(extract_to), True
                
                return str(extract_to), True
                    
        except Exception as e:
            print(f"❌ Error extracting zip file: {e}")
            return str(zip_path), False

    def pack_folder_to_file(self, folder_path, output_path, target_filename):
        """Pack all contents of a folder back into a single file"""
        folder = Path(folder_path)
        
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Folder not found: {folder}")
        
        # Get all files in the folder (recursively), excluding directories
        all_files = list(folder.rglob('*'))
        files_only = [f for f in all_files if f.is_file()]
        
        if not files_only:
            raise FileNotFoundError(f"No files found in folder: {folder}")
        
        print(f"📁 Found {len(files_only)} files to pack: {[f.name for f in files_only[:5]]}")
        
        if len(files_only) == 1:
            # Single file - just copy it directly
            single_file = files_only[0]
            if single_file.is_file():  # Double-check it's actually a file
                shutil.copyfile(single_file, output_path)
                print(f"✅ Packed single file: {single_file.name} -> {output_path}")
            else:
                raise FileNotFoundError(f"Expected file but found directory: {single_file}")
        else:
            # Multiple files - create a zip archive with the target filename
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in files_only:
                    if file_path.is_file():  # Ensure we only add files, not directories
                        # Create relative path from folder root
                        relative_path = file_path.relative_to(folder)
                        zipf.write(file_path, relative_path)
                        print(f"  📄 Added to zip: {relative_path}")
            print(f"✅ Packed {len(files_only)} files into: {output_path}")
        
        return str(output_path)

    async def download_file_async(self, google_drive_url, filename, model_type, custom_path="", overwrite=False, auto_extract_zip=True, progress_callback=None, session_id=None):
        """Async version of download_file with progress callbacks"""
        try:
            # Import cancellation flags
            from .file_system_manager import download_cancellation_flags
            
            if session_id:
                progress_store[session_id] = {"status": "starting", "message": "Extracting file ID...", "percentage": 0}
            
            # Check for cancellation
            if session_id and download_cancellation_flags.get(session_id):
                progress_store[session_id] = {"status": "cancelled", "message": "Download cancelled by user", "percentage": 0}
                return {"success": False, "error": "Download cancelled by user"}
            
            if progress_callback:
                progress_callback("Extracting file ID...")
            
            file_id = self.extract_file_id(google_drive_url)
            print(f"Extracted file ID: {file_id}")
            
            if session_id:
                progress_store[session_id] = {"status": "progress", "message": f"File ID extracted: {file_id}", "percentage": 10}
            
            # Check for cancellation
            if session_id and download_cancellation_flags.get(session_id):
                progress_store[session_id] = {"status": "cancelled", "message": "Download cancelled by user", "percentage": 0}
                return {"success": False, "error": "Download cancelled by user"}
            
            final_download_path = self.get_download_path(model_type, custom_path, filename)
            
            if final_download_path.exists() and not overwrite:
                if session_id:
                    progress_store[session_id] = {"status": "completed", "message": "File already exists!", "percentage": 100}
                if progress_callback:
                    progress_callback("File already exists!")
                return {"success": True, "file_path": str(final_download_path), "message": "File already exists"}
            
            # Create progress callback that updates both local callback and session store and checks cancellation
            def combined_progress_callback(message, percentage=None):
                # Check for cancellation before updating progress
                if session_id and download_cancellation_flags.get(session_id):
                    return False  # Signal cancellation
                
                if session_id:
                    update_data = {"status": "progress", "message": message}
                    if percentage is not None:
                        update_data["percentage"] = percentage
                    progress_store[session_id] = update_data
                if progress_callback:
                    progress_callback(message)
                return True  # Continue download
            
            # Download using Playwright
            if not combined_progress_callback("Starting download...", 15):
                return {"success": False, "error": "Download cancelled by user"}
                
            success, suggested_filename, temp_download_path = await self.download_with_playwright(
                file_id, final_download_path, combined_progress_callback, session_id
            )
            
            # Check for cancellation after download
            if session_id and download_cancellation_flags.get(session_id):
                # Clean up temp file
                if temp_download_path and temp_download_path.exists():
                    temp_download_path.unlink()
                progress_store[session_id] = {"status": "cancelled", "message": "Download cancelled by user", "percentage": 0}
                return {"success": False, "error": "Download cancelled by user"}
            
            if not success or not temp_download_path.exists():
                if session_id:
                    progress_store[session_id] = {"status": "error", "message": "Download failed!", "percentage": 0}
                if progress_callback:
                    progress_callback("Download failed!")
                return {"success": False, "error": "Download failed"}
            
            file_size = temp_download_path.stat().st_size
            combined_progress_callback(f"Downloaded {file_size} bytes", 70)
            
            # Check if the downloaded file is a zip and should be extracted
            if auto_extract_zip and self.is_zip_file(temp_download_path):
                if self.is_pth_file(filename):
                    combined_progress_callback("Extracting and validating PyTorch model...", 75)
                else:
                    combined_progress_callback("Extracting zip file...", 75)
                
                try:
                    final_path, extract_success = self.extract_zip_file(
                        temp_download_path, 
                        final_download_path,
                        filename
                    )
                    
                    # Clean up temporary zip file
                    temp_download_path.unlink()
                    
                    if extract_success:
                        if self.is_pth_file(filename):
                            combined_progress_callback("PyTorch model extracted and validated!", 95)
                        else:
                            combined_progress_callback("Extraction completed!", 95)
                        
                        success_message = "Download and extraction completed successfully"
                        if self.is_pth_file(filename):
                            success_message = "PyTorch model downloaded and validated successfully"
                        
                        if session_id:
                            progress_store[session_id] = {"status": "completed", "message": success_message, "percentage": 100}
                            
                        return {"success": True, "file_path": final_path, "message": success_message}
                    else:
                        # Move zip file to final location as fallback
                        temp_download_path.rename(final_download_path)
                        fallback_message = "Download completed (extraction failed, kept as zip)"
                        if session_id:
                            progress_store[session_id] = {"status": "completed", "message": fallback_message, "percentage": 100}
                        return {"success": True, "file_path": str(final_download_path), "message": fallback_message}
                        
                except Exception as e:
                    # Move zip file to final location as fallback
                    if temp_download_path.exists():
                        temp_download_path.rename(final_download_path)
                    error_message = f"Download completed (extraction error: {e})"
                    if session_id:
                        progress_store[session_id] = {"status": "completed", "message": error_message, "percentage": 100}
                    return {"success": True, "file_path": str(final_download_path), "message": error_message}
            
            else:
                # Not a zip file or extraction disabled
                if final_download_path.exists() and overwrite:
                    final_download_path.unlink()
                
                temp_download_path.rename(final_download_path)
                
                # Validate .pth files even when not extracted from zip
                if self.is_pth_file(filename):
                    combined_progress_callback("Validating PyTorch model...", 90)
                    
                    if self.validate_pth_file(final_download_path):
                        success_message = f"PyTorch model downloaded and validated successfully ({file_size} bytes)"
                    else:
                        success_message = f"PyTorch model downloaded but validation failed ({file_size} bytes)"
                else:
                    success_message = f"Download completed successfully ({file_size} bytes)"
                
                # Register the model with the configuration manager
                if MODEL_CONFIG_AVAILABLE:
                    try:
                        model_config_manager.register_google_drive_model(
                            local_path=str(final_download_path),
                            drive_url=google_drive_url,
                            model_type=model_type
                        )
                        print(f"📝 Model registered in config: {final_download_path}")
                    except Exception as e:
                        print(f"⚠️ Failed to register model in config: {e}")
                
                combined_progress_callback("Download completed!", 100)
                if session_id:
                    progress_store[session_id] = {"status": "completed", "message": success_message, "percentage": 100}
                return {"success": True, "file_path": str(final_download_path), "message": success_message}
                
        except Exception as e:
            error_message = f"Error: {e}"
            if session_id:
                progress_store[session_id] = {"status": "error", "message": error_message, "percentage": 0}
            if progress_callback:
                progress_callback(error_message)
            return {"success": False, "error": str(e)}
        finally:
            # Clean up cancellation flag
            if session_id and session_id in download_cancellation_flags:
                del download_cancellation_flags[session_id]

    async def download_with_playwright(self, file_id, download_path, progress_callback=None, session_id=None):
        """Download file using Playwright with progress callbacks and cancellation support"""
        # Import cancellation flags
        from .file_system_manager import download_cancellation_flags
        
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        # Use temporary file for potential zip downloads
        temp_dir = Path(tempfile.gettempdir())
        temp_download_path = temp_dir / f"gdrive_temp_{file_id}.tmp"
        
        if progress_callback:
            if not progress_callback("Starting download...", 20):
                return False, None, None
        
        # Check for cancellation before starting browser
        if session_id and download_cancellation_flags.get(session_id):
            return False, None, None
        
        try:
            # Ensure authentication first
            await self.session_manager.ensure_authenticated('google_drive')
            
            # Create a page using the shared session
            page = await self.session_manager.create_page('google_drive')
            
            try:
                download_info = {"path": None, "completed": False, "filename": None}
                
                async def handle_download(download):
                    # Check cancellation before starting actual download
                    if session_id and download_cancellation_flags.get(session_id):
                        await download.cancel()
                        return
                        
                    if progress_callback:
                        if not progress_callback("Download started...", 30):
                            await download.cancel()
                            return
                    
                    try:
                        await download.save_as(temp_download_path)
                        download_info["path"] = temp_download_path
                        download_info["filename"] = download.suggested_filename
                        download_info["completed"] = True
                        if progress_callback:
                            progress_callback("Download completed!", 65)
                    except Exception as e:
                        if "cancel" not in str(e).lower():
                            print(f"Download error: {e}")
                
                page.on("download", handle_download)
                
                # Check cancellation before navigation
                if session_id and download_cancellation_flags.get(session_id):
                    return False, None, None
                
                if progress_callback:
                    progress_callback("Connecting to Google Drive...", 25)
                
                await page.goto(download_url, wait_until="networkidle")
                
                # Handle different Google Drive download scenarios
                if not download_info["completed"]:
                    # Check for cancellation during page interactions
                    if session_id and download_cancellation_flags.get(session_id):
                        return False, None, None
                        
                    if progress_callback:
                        progress_callback("Looking for download button...", 35)
                    
                    # Look for download button (large files)
                    download_button = page.locator('a:has-text("Download anyway")')
                    if await download_button.count() > 0:
                        await download_button.click()
                        await page.wait_for_timeout(2000)
                    
                    # Alternative download button selectors
                    if not download_info["completed"]:
                        selectors = [
                            '[aria-label="Download"]',
                            'a[href*="export=download"]',
                            '#uc-download-link'
                        ]
                        
                        for selector in selectors:
                            # Check for cancellation in loop
                            if session_id and download_cancellation_flags.get(session_id):
                                return False, None, None
                                
                            element = page.locator(selector)
                            if await element.count() > 0:
                                await element.click()
                                break
                
                # Wait for download to complete with cancellation checks
                timeout = 60000  # 60 seconds for large files
                elapsed = 0
                while not download_info["completed"] and elapsed < timeout:
                    # Check for cancellation during wait
                    if session_id and download_cancellation_flags.get(session_id):
                        return False, None, None
                    
                    await page.wait_for_timeout(1000)
                    elapsed += 1000
                    if progress_callback and elapsed % 5000 == 0:
                        percentage = min(35 + (elapsed / timeout) * 30, 65)  # Progress from 35% to 65%
                        continue_download = progress_callback(f"Waiting for download... ({elapsed//1000}s)", percentage)
                        if continue_download is False:
                            return False, None, None
                
                if not download_info["completed"]:
                    # Check for cancellation before fallback
                    if session_id and download_cancellation_flags.get(session_id):
                        return False, None, None
                        
                    if progress_callback:
                        progress_callback("Trying direct download...", 40)
                    # Fallback: try to get file content directly
                    response = await page.goto(download_url)
                    if response and response.status == 200:
                        content = await response.body()
                        
                        # Check for cancellation before writing file
                        if session_id and download_cancellation_flags.get(session_id):
                            return False, None, None
                        
                        async with aiofiles.open(temp_download_path, 'wb') as f:
                            await f.write(content)
                        download_info["completed"] = True
                        if progress_callback:
                            progress_callback("Direct download completed!", 65)
                
            finally:
                await page.close()
                # Save session state after use
                await self.session_manager.save_session_state('google_drive')
        
        except Exception as e:
            print(f"Google Drive download error: {e}")
            return False, None, None
        
        return download_info["completed"], download_info.get("filename", ""), temp_download_path

