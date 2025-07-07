import asyncio
from .utils import CivitAIUtils
from .downloader import CivitAIDownloader
from .progress import ProgressTracker
from ..shared_state import download_cancellation_flags

class CivitAIDownloadAPI:
    def __init__(self):
        self.utils = CivitAIUtils()
        self.downloader = CivitAIDownloader()

    async def download_from_civitai(self, civitai_url: str, target_fsm_path: str, 
                                   filename: str = None, overwrite: bool = False, 
                                   session_id: str = None, user_token: str = None, progress_callback=None):
        """Download a model from CivitAI with progress tracking and optional progress callback"""
        try:
            # Check for cancellation at the start
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
                
            ProgressTracker.update_progress(session_id, "Parsing CivitAI URL...", 5)
            
            # Parse the URL to extract model and version IDs
            parsed_url = self.utils.parse_civitai_url(civitai_url)
            
            # Check for cancellation
            if session_id and download_cancellation_flags.get(session_id):
                ProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            # Use environment token by default, user token only if provided
            import os
            token_to_use = os.environ.get("CIVITAI_API_KEY")
            
            if user_token:
                token_to_use = user_token
                print(f"ℹ️ Using user-provided CIVITAI_API_KEY for CivitAI authentication.")
            elif token_to_use:
                print(f"ℹ️ Using environment CIVITAI_API_KEY for CivitAI authentication.")
            
            # Resolve FSM relative path - target_fsm_path is the full FSM path like "models/loras"
            if not target_fsm_path:
                raise ValueError("Target path is required")
            
            # Handle direct download URLs
            if parsed_url.get("is_direct_download"):
                version_id = parsed_url["version_id"]
                direct_download_url = parsed_url.get("download_url")
                
                ProgressTracker.update_progress(
                    session_id,
                    f"Direct download URL detected (Version ID: {version_id})",
                    10
                )
                
                # Call external progress callback if provided
                if progress_callback:
                    progress_callback(session_id, f"Direct download URL detected (Version ID: {version_id})", 10)
                
                # Download using direct URL with cancellation support
                result = await self.downloader.download_model_async(
                    model_id=None,  # Not needed for direct downloads
                    version_id=version_id,
                    target_fsm_path=target_fsm_path,
                    filename=filename,
                    token=token_to_use,
                    session_id=session_id,
                    direct_download_url=direct_download_url,
                    progress_callback=progress_callback
                )
                
                return result
            else:
                # Handle regular model/version URLs with cancellation support
                model_id = parsed_url["model_id"]
                version_id = parsed_url["version_id"]
                
                ProgressTracker.update_progress(
                    session_id,
                    f"Model ID: {model_id}" + (f", Version ID: {version_id}" if version_id else " (latest version)"),
                    10
                )
                
                # Call external progress callback if provided
                if progress_callback:
                    progress_callback(session_id, f"Model ID: {model_id}" + (f", Version ID: {version_id}" if version_id else " (latest version)"), 10)
                
                # Download the model with cancellation support
                result = await self.downloader.download_model_async(
                    model_id=model_id,
                    version_id=version_id,
                    target_fsm_path=target_fsm_path,
                    filename=filename,
                    token=token_to_use,
                    session_id=session_id,
                    progress_callback=progress_callback
                )
                
                return result
            
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
            if session_id and session_id in download_cancellation_flags:
                del download_cancellation_flags[session_id]
