import asyncio
import shutil
from pathlib import Path
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError
from .utils import HuggingFaceUtils
from .browser_automation import BrowserAutomation
from .downloader import HuggingFaceDownloader
from .progress import ProgressTracker

class HuggingFaceDownloadAPI:
    def __init__(self):
        self.utils = HuggingFaceUtils()
        self.browser_automation = BrowserAutomation()
        self.downloader = HuggingFaceDownloader()

    async def download_from_huggingface(self, hf_url: str, target_fsm_path: str, overwrite: bool = False, session_id: str = None, user_token: str = None):
        # Reset session directory for each new download to group screenshots by download session
        self.browser_automation.screenshot_manager.current_session_dir = None
        
        loop = asyncio.get_event_loop()
        
        # Import cancellation flags
        from ..file_system_manager import download_cancellation_flags
        
        # Use user-provided token if available, otherwise fall back to environment token
        import os
        token_to_use = user_token or os.environ.get("HF_TOKEN")

        try:
            # Check for cancellation at the start
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
                
            ProgressTracker.update_progress(session_id, "Parsing Hugging Face URL...", 5)
            
            parsed_url = self.utils.parse_hf_url(hf_url)
            repo_id = parsed_url["repo_id"]
            filename_in_repo = parsed_url["filename"]
            is_file_url = parsed_url["is_file_url"]

            # Check for cancellation
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}

            ProgressTracker.update_progress(session_id, f"Repo: {repo_id}, File: {filename_in_repo or 'All'}", 10)

            # Always attempt access check with Playwright first, but don't fail on errors
            try:
                has_access, needed_auth, access_error = await self.browser_automation.check_hf_access_with_playwright(hf_url, session_id)
                
                if not has_access and not user_token:
                    error_msg = """We are unable to download the package because access is restricted by the owner. Give us some time so that we request access manually. If you need it ASAP you can still input your own Hugging Face access token below. We will download it on your behalf. Make sure you requested and got access to the package before proceeding.<br><br>Note that we don't store your Hugging Face token on our servers."""
                    ProgressTracker.set_access_restricted(session_id, error_msg)
                    return {"success": False, "error": error_msg, "error_type": "access_restricted"}
            except Exception as playwright_error:
                print(f"⚠️ Playwright access check failed: {playwright_error}")
                ProgressTracker.update_progress(session_id, "Access check failed, attempting direct download...", 15)

            # The final destination directory within FSM
            fsm_target_dir_abs = self.utils.get_target_path(target_fsm_path)

            if token_to_use:
                token_source = "user-provided" if user_token else "environment"
                print(f"ℹ️ Using {token_source} HF_TOKEN for Hugging Face authentication.")

            if is_file_url:
                # Download a single file with cancellation support
                ProgressTracker.update_progress(session_id, f"Starting download of file: {filename_in_repo}", 75)
                
                final_file_path_abs = fsm_target_dir_abs / Path(filename_in_repo).name

                if final_file_path_abs.exists() and not overwrite:
                    ProgressTracker.set_completed(session_id, "File already exists.")
                    return {"success": True, "message": "File already exists.", "path": str(final_file_path_abs)}

                def hf_download_progress_callback(current_size, total_size):
                    # Check for cancellation in progress callback
                    if session_id and download_cancellation_flags.get(session_id):
                        return False  # Signal to stop download
                        
                    is_total_size_reliable = total_size > 1024

                    if is_total_size_reliable:
                        percentage_ratio_current = min(current_size, total_size)
                        percentage = 75 + int((percentage_ratio_current / total_size) * 15)
                        
                        downloaded_formatted = self.utils.format_file_size(current_size)
                        total_formatted = self.utils.format_file_size(total_size)
                        message = f"Downloading {filename_in_repo}: {downloaded_formatted}/{total_formatted}"
                    else:
                        percentage = 75 
                        downloaded_formatted = self.utils.format_file_size(current_size)
                        message = f"Downloading {filename_in_repo}: {downloaded_formatted} (total size unknown)"
                    
                    # Create a proper closure to capture the values
                    def update_progress_safe():
                        ProgressTracker.update_progress(session_id, message, percentage)
                    
                    # Schedule progress update on the main event loop
                    if loop.is_running():
                        try:
                            loop.call_soon_threadsafe(update_progress_safe)
                        except RuntimeError:
                            # Fallback if call_soon_threadsafe fails
                            ProgressTracker.update_progress(session_id, message, percentage)
                    else:
                        ProgressTracker.update_progress(session_id, message, percentage)
                    
                    return True  # Continue download

                try:
                    temp_file_path = await loop.run_in_executor(
                        None, 
                        lambda: self.downloader.download_with_progress(
                            repo_id=repo_id,
                            filename=filename_in_repo,
                            token=token_to_use,
                            progress_callback=hf_download_progress_callback,
                            session_id=session_id  # Pass session_id for cancellation checks
                        )
                    )
                except Exception as download_error:
                    # Check if it was cancelled
                    if session_id and download_cancellation_flags.get(session_id):
                        ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                        return {"success": False, "error": "Download cancelled by user"}
                        
                    error_str = str(download_error).lower()
                    if "403" in error_str or "forbidden" in error_str or "access" in error_str:
                        if user_token:
                            error_msg = "Access denied even with provided token. Please ensure your token has access to this repository and is valid."
                        else:
                            error_msg = """We are unable to download the package because access is restricted by the owner. Give us some time so that we request access manually. If you need it ASAP you can still input your own Hugging Face access token below. We will download it on your behalf. Make sure you requested and got access to the package before proceeding.<br><br>Note that we don't store your Hugging Face token on our servers."""
                        
                        ProgressTracker.set_access_restricted(session_id, error_msg)
                        return {"success": False, "error": error_msg, "error_type": "access_restricted"}
                    else:
                        raise download_error

                # Check for cancellation before moving file
                if session_id and download_cancellation_flags.get(session_id):
                    # Clean up temp file
                    if temp_file_path and Path(temp_file_path).exists():
                        Path(temp_file_path).unlink()
                    ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}

                ProgressTracker.update_progress(session_id, f"File downloaded, moving to final location...", 90)

                final_file_path_abs.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(temp_file_path, final_file_path_abs)
                ProgressTracker.update_progress(session_id, f"File moved to: {final_file_path_abs}", 95)
                
                ProgressTracker.set_completed(session_id, f"File '{filename_in_repo}' downloaded successfully.")
                return {"success": True, "message": f"File '{filename_in_repo}' downloaded.", "path": str(final_file_path_abs)}

            else:
                # Download entire repository with progress tracking
                ProgressTracker.update_progress(session_id, f"Starting download of repository: {repo_id}", 75)

                def repo_download_progress_callback(downloaded_size, total_size):
                    # For repository downloads, show current size progress without percentages
                    if downloaded_size is not None:
                        downloaded_formatted = self.utils.format_file_size(downloaded_size)
                        
                        if total_size is not None and total_size > 0 and downloaded_size == total_size:
                            # This is the completion signal
                            percentage = 90
                            message = f"Repository downloaded: {downloaded_formatted} (completed)"
                        else:
                            # Show progress without percentage calculation
                            percentage = 85  # Fixed progress during download
                            message = f"Downloading repository: {downloaded_formatted}"
                    else:
                        percentage = 75
                        message = f"Downloading repository..."
                    
                    # Create a proper closure to capture the values
                    def update_progress_safe():
                        ProgressTracker.update_progress(session_id, message, percentage)
                    
                    # Schedule progress update on the main event loop
                    if loop.is_running():
                        try:
                            loop.call_soon_threadsafe(update_progress_safe)
                        except RuntimeError:
                            # Fallback if call_soon_threadsafe fails
                            ProgressTracker.update_progress(session_id, message, percentage)
                    else:
                        ProgressTracker.update_progress(session_id, message, percentage)

                try:
                    # Use the async version directly instead of running in executor
                    repo_snapshot_cache_path_str = await self.downloader.snapshot_download_with_progress_async(
                        repo_id=repo_id,
                        token=token_to_use,
                        progress_callback=repo_download_progress_callback
                    )
                except Exception as download_error:
                    error_str = str(download_error).lower()
                    if "403" in error_str or "forbidden" in error_str or "access" in error_str:
                        if user_token:
                            error_msg = "Access denied even with provided token. Please ensure your token has access to this repository and is valid."
                        else:
                            error_msg = """We are unable to download the package because access is restricted by the owner. Give us some time so that we request access manually. If you need it ASAP you can still input your own Hugging Face access token below. We will download it on your behalf. Make sure you requested and got access to the package before proceeding.<br><br>Note that we don't store your Hugging Face token on our servers."""
                        
                        ProgressTracker.set_access_restricted(session_id, error_msg)
                        return {"success": False, "error": error_msg, "error_type": "access_restricted"}
                    else:
                        raise download_error

                repo_snapshot_cache_path = Path(repo_snapshot_cache_path_str)
                ProgressTracker.update_progress(session_id, f"Repository downloaded, copying to target location...", 90)

                repo_name = repo_id.split('/')[-1]
                repo_target_dir = fsm_target_dir_abs / repo_name
                
                if repo_target_dir.exists():
                    if not overwrite:
                        ProgressTracker.update_progress(session_id, f"Repository folder '{repo_name}' already exists. Skipping.", 95)
                        try:
                            shutil.rmtree(repo_snapshot_cache_path)
                        except Exception as cleanup_error:
                            print(f"⚠️ Failed to clean up repository cache: {cleanup_error}")
                        
                        ProgressTracker.set_completed(session_id, f"Repository '{repo_name}' already exists at target location.")
                        return {"success": True, "message": f"Repository '{repo_name}' already exists.", "path": str(repo_target_dir)}
                    else:
                        shutil.rmtree(repo_target_dir)
                        print(f"🗑️ Removed existing repository folder: {repo_target_dir}")

                repo_target_dir.mkdir(parents=True, exist_ok=True)

                total_items = list(repo_snapshot_cache_path.iterdir())
                for i, item_in_cache in enumerate(total_items):
                    # Check for cancellation during file copying
                    if session_id and download_cancellation_flags.get(session_id):
                        ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                        return {"success": False, "error": "Download cancelled by user"}
                    
                    progress_percent = 90 + int((i / len(total_items)) * 5)
                    ProgressTracker.update_progress(session_id, f"Copying {item_in_cache.name} to {repo_name} ({i+1}/{len(total_items)})", progress_percent)
                    
                    target_item_path = repo_target_dir / item_in_cache.name
                    
                    if item_in_cache.is_dir():
                        shutil.copytree(item_in_cache, target_item_path)
                    else:
                        shutil.copy2(item_in_cache, target_item_path)

                try:
                    shutil.rmtree(repo_snapshot_cache_path)
                    print(f"🗑️ Cleaned up repository cache: {repo_snapshot_cache_path}")
                except Exception as cleanup_error:
                    print(f"⚠️ Failed to clean up repository cache {repo_snapshot_cache_path}: {cleanup_error}")
                
                ProgressTracker.update_progress(session_id, f"Repository '{repo_name}' copied to: {repo_target_dir}", 95)
                ProgressTracker.set_completed(session_id, f"Repository '{repo_name}' downloaded successfully.")
                return {"success": True, "message": f"Repository '{repo_name}' downloaded.", "path": str(repo_target_dir)}

        except (EntryNotFoundError, RepositoryNotFoundError) as e:
            error_msg = f"Hugging Face error: {str(e)}"
            ProgressTracker.set_error(session_id, error_msg)
            return {"success": False, "error": error_msg}
        except ValueError as e:
            error_msg = str(e)
            ProgressTracker.set_error(session_id, error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"An unexpected error occurred: {str(e)}"
            ProgressTracker.set_error(session_id, error_msg)
            return {"success": False, "error": error_msg}
        finally:
            # Clean up cancellation flag
            if session_id and session_id in download_cancellation_flags:
                del download_cancellation_flags[session_id]
