import os
import re
import sys
import subprocess
import threading
import tempfile
import shutil
from pathlib import Path
from huggingface_hub import hf_hub_download, snapshot_download, get_hf_file_metadata, hf_hub_url
from huggingface_hub.utils import hf_raise_for_status
from huggingface_hub.constants import HUGGINGFACE_CO_URL_HOME
import requests
from .utils import HuggingFaceUtils
from ..shared_state import download_cancellation_flags

class HuggingFaceDownloader:
    def __init__(self):
        self.utils = HuggingFaceUtils()
        
        # Ensure hf_transfer is enabled if available
        try:
            import hf_transfer
            os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
            print("✅ hf_transfer enabled for Hugging Face downloads.")
        except ImportError:
            print("ℹ️ hf_transfer not available. Downloads may be slower. Consider `pip install hf-transfer`.")
            os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

    def download_with_progress(self, repo_id: str, filename: str, token: str = None, progress_callback=None, session_id: str = None):
        """Download a single file with progress tracking"""
        use_hf_transfer = os.environ.get("HF_HUB_ENABLE_HF_TRANSFER", "0") == "1"
        
        try:
            # Check for cancellation at the start
            if session_id and download_cancellation_flags.get(session_id):
                raise Exception("Download cancelled by user")

            if use_hf_transfer:
                print("🚀 Using hf_transfer for faster download with progress tracking")
                try:
                    temp_file_path = self._download_with_hf_transfer_progress(
                        repo_id=repo_id,
                        filename=filename,
                        token=token,
                        progress_callback=progress_callback,
                        session_id=session_id
                    )
                    return temp_file_path
                    
                except Exception as hf_transfer_error:
                    # Check if it was cancellation
                    if session_id and download_cancellation_flags.get(session_id):
                        raise Exception("Download cancelled by user")
                    print(f"hf_transfer download failed: {hf_transfer_error}. Falling back to custom progress tracking.")
            
            print("📡 Using custom progress tracking for download")
            return self._download_with_custom_progress(repo_id, filename, token, progress_callback, session_id)
                
        except Exception as e:
            if "cancelled" in str(e).lower():
                raise e
            print(f"Download with progress failed: {e}. Falling back to standard hf_hub_download.")
            return self._fallback_download(repo_id, filename, token, session_id)

    def _download_with_custom_progress(self, repo_id: str, filename: str, token: str = None, progress_callback=None, session_id: str = None):
        """Custom progress tracking implementation"""
        total_size = 0
        actual_download_url = None

        try:
            # Check for cancellation before metadata request
            if session_id and download_cancellation_flags.get(session_id):
                raise Exception("Download cancelled by user")
                
            metadata_url = hf_hub_url(repo_id=repo_id, filename=filename, token=token)
            metadata = get_hf_file_metadata(url=metadata_url, token=token)
            
            if metadata.size is not None and metadata.size > 0:
                total_size = metadata.size
                actual_download_url = metadata_url 
                print(f"File size from metadata: {self.utils.format_file_size(total_size)} for URL: {actual_download_url}")
            else:
                print(f"get_hf_file_metadata returned size: {metadata.size}. Will try HEAD request.")
        except Exception as meta_exc:
            print(f"Could not get metadata: {meta_exc}. Falling back to HEAD request.")

        session = requests.Session()
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})

        if total_size <= 0: 
            # Check for cancellation before HEAD request
            if session_id and download_cancellation_flags.get(session_id):
                raise Exception("Download cancelled by user")
                
            head_url_for_fallback = f"{HUGGINGFACE_CO_URL_HOME}/{repo_id}/resolve/main/{filename}"
            if actual_download_url is None: 
                actual_download_url = head_url_for_fallback

            try:
                print(f"Attempting HEAD request on: {head_url_for_fallback}")
                head_response = session.head(head_url_for_fallback, allow_redirects=True, timeout=10)
                hf_raise_for_status(head_response)
                
                content_length_str = head_response.headers.get('content-length')
                if content_length_str:
                    total_size = int(content_length_str)
                    print(f"File size from HEAD: {self.utils.format_file_size(total_size)}")
                    if actual_download_url == head_url_for_fallback and head_response.url != head_url_for_fallback:
                         print(f"HEAD request redirected to: {head_response.url}")
                         actual_download_url = head_response.url
                else:
                    print(f"Content-Length not found in HEAD response.")
                    total_size = 0
            except Exception as head_exc:
                print(f"HEAD request failed: {head_exc}. Proceeding with unknown size.")
                if actual_download_url is None:
                    actual_download_url = head_url_for_fallback
                total_size = 0

        if actual_download_url is None:
            actual_download_url = f"{HUGGINGFACE_CO_URL_HOME}/{repo_id}/resolve/main/{filename}"
            print(f"Using default resolve URL: {actual_download_url}")

        print(f"Starting download from: {actual_download_url} (expected size: {self.utils.format_file_size(total_size)})")
        
        safe_suffix = f"_{Path(filename).name}"

        with tempfile.NamedTemporaryFile(delete=False, suffix=safe_suffix) as temp_file:
            # Check for cancellation before starting download
            if session_id and download_cancellation_flags.get(session_id):
                temp_file.close()
                Path(temp_file.name).unlink(missing_ok=True)
                raise Exception("Download cancelled by user")
                
            response = session.get(actual_download_url, stream=True, timeout=30)
            hf_raise_for_status(response)
            
            get_content_length_str = response.headers.get('content-length')
            if get_content_length_str:
                get_total_size = int(get_content_length_str)
                if get_total_size > 0:
                    if total_size <= 0 or abs(get_total_size - total_size) > total_size * 0.1:
                        print(f"GET Content-Length ({self.utils.format_file_size(get_total_size)}) is more reliable. Updating total_size.")
                        total_size = get_total_size
            
            downloaded = 0
            chunk_size = 1024 * 1024  # 1MB chunks for better performance
            last_progress_call = 0
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                # Check for cancellation on each chunk
                if session_id and download_cancellation_flags.get(session_id):
                    temp_file.close()
                    Path(temp_file.name).unlink(missing_ok=True)
                    raise Exception("Download cancelled by user")
                
                if chunk:
                    temp_file.write(chunk)
                    downloaded += len(chunk)
                    
                    # Call progress callback with cancellation check
                    if progress_callback:
                        print(f"📊 Download progress: {self.utils.format_file_size(downloaded)} / {self.utils.format_file_size(total_size)} ({downloaded}/{total_size} bytes)")
                        # Progress callback should return False to signal cancellation
                        continue_download = progress_callback(downloaded, total_size)
                        if continue_download is False:
                            temp_file.close()
                            Path(temp_file.name).unlink(missing_ok=True)
                            raise Exception("Download cancelled by user")
                        last_progress_call = downloaded
            
            # Ensure final progress call
            if progress_callback and downloaded > last_progress_call:
                print(f"📊 Final download progress: {self.utils.format_file_size(downloaded)} / {self.utils.format_file_size(total_size)}")
                progress_callback(downloaded, total_size)
            
            temp_file_path = temp_file.name
        
        return temp_file_path

    def _download_with_hf_transfer_progress(self, repo_id: str, filename: str, token: str = None, progress_callback=None, session_id: str = None):
        """Download using hf_transfer with progress tracking via subprocess output capture"""
        safe_suffix = f"_{Path(filename).name}"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=safe_suffix)
        temp_file_path = temp_file.name
        temp_file.close()
        
        try:
            # Check for cancellation before starting
            if session_id and download_cancellation_flags.get(session_id):
                Path(temp_file_path).unlink(missing_ok=True)
                raise Exception("Download cancelled by user")
                
            cached_path = self._run_hf_download_with_progress_capture(
                repo_id=repo_id,
                filename=filename,
                token=token,
                progress_callback=progress_callback,
                session_id=session_id
            )
            
            # Check for cancellation after download
            if session_id and download_cancellation_flags.get(session_id):
                self.utils.cleanup_cache_file(cached_path)
                Path(temp_file_path).unlink(missing_ok=True)
                raise Exception("Download cancelled by user")
            
            if os.path.exists(cached_path):
                shutil.copy2(cached_path, temp_file_path)
                self.utils.cleanup_cache_file(cached_path)
                return temp_file_path
            else:
                raise FileNotFoundError(f"Downloaded file not found: {cached_path}")
                
        except Exception as e:
            try:
                os.unlink(temp_file_path)
            except:
                pass
            raise e

    def _run_hf_download_with_progress_capture(self, repo_id: str, filename: str, token: str = None, progress_callback=None, session_id: str = None):
        """Run hf_hub_download in a subprocess to capture hf_transfer output"""
        download_script = f'''
import os
import sys
from huggingface_hub import hf_hub_download

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

try:
    result = hf_hub_download(
        repo_id="{repo_id}",
        filename="{filename}",
        token="{token}" if "{token}" else None,
        local_dir_use_symlinks=False
    )
    print(f"DOWNLOAD_COMPLETE:{result}")
except Exception as e:
    print(f"DOWNLOAD_ERROR:{e}")
    sys.exit(1)
'''
        
        process = subprocess.Popen(
            [sys.executable, "-c", download_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        downloaded_path = None
        total_size = 0
        current_size = 0
        
        def track_progress():
            nonlocal downloaded_path, total_size, current_size
            
            for line in iter(process.stdout.readline, ''):
                # Check for cancellation during progress tracking
                if session_id and download_cancellation_flags.get(session_id):
                    print("🚫 Cancellation detected, terminating subprocess")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise Exception("Download cancelled by user")
                
                line = line.strip()
                if not line:
                    continue
                    
                print(f"hf_transfer output: {line}")
                
                if "DOWNLOAD_COMPLETE:" in line:
                    downloaded_path = line.split("DOWNLOAD_COMPLETE:", 1)[1]
                    if progress_callback:
                        continue_download = progress_callback(current_size or total_size, total_size or current_size)
                        if continue_download is False:
                            process.terminate()
                            raise Exception("Download cancelled by user")
                    break
                elif "DOWNLOAD_ERROR:" in line:
                    error_msg = line.split("DOWNLOAD_ERROR:", 1)[1]
                    raise Exception(f"Download failed: {error_msg}")
                else:
                    progress_info = self._parse_hf_transfer_output(line)
                    if progress_info:
                        if progress_info.get('total_size'):
                            total_size = progress_info['total_size']
                        if progress_info.get('current_size'):
                            current_size = progress_info['current_size']
                        
                        if progress_callback and total_size > 0:
                            continue_download = progress_callback(current_size, total_size)
                            if continue_download is False:
                                process.terminate()
                                raise Exception("Download cancelled by user")
        
        progress_thread = threading.Thread(target=track_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        return_code = process.wait()
        progress_thread.join(timeout=5)
        
        if return_code != 0:
            raise Exception(f"Download process failed with return code {return_code}")
        
        if not downloaded_path:
            raise Exception("Download completed but path not found")
            
        return downloaded_path

    def _fallback_download(self, repo_id: str, filename: str, token: str = None, session_id: str = None):
        """Final fallback to standard hf_hub_download"""
        # Import cancellation flags
        
        # Check for cancellation before fallback
        if session_id and download_cancellation_flags.get(session_id):
            raise Exception("Download cancelled by user")
        
        cached_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            token=token,
            local_dir_use_symlinks=False
        )
        
        # Check for cancellation after download
        if session_id and download_cancellation_flags.get(session_id):
            self.utils.cleanup_cache_file(cached_path)
            raise Exception("Download cancelled by user")
        
        safe_fallback_suffix = f"_{Path(filename).name}"
        if os.path.islink(cached_path):
            actual_path = os.path.realpath(cached_path)
            if os.path.exists(actual_path):
                with tempfile.NamedTemporaryFile(delete=False, suffix=safe_fallback_suffix) as temp_file:
                    shutil.copy2(actual_path, temp_file.name)
                    self.utils.cleanup_cache_file(cached_path, actual_path)
                    return temp_file.name
            else:
                raise FileNotFoundError(f"Symlink target does not exist: {actual_path}")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=safe_fallback_suffix) as temp_file:
                shutil.copy2(cached_path, temp_file.name)
                self.utils.cleanup_cache_file(cached_path)
                return temp_file.name

    async def snapshot_download_with_progress_async(self, repo_id: str, token: str = None, progress_callback=None):
        """Async version of snapshot download with proper progress tracking"""
        use_hf_transfer = os.environ.get("HF_HUB_ENABLE_HF_TRANSFER", "0") == "1"
        
        if use_hf_transfer:
            print("🚀 Using hf_transfer for repository download with progress tracking")
            try:
                return await self._snapshot_download_with_hf_transfer_progress_async(
                    repo_id=repo_id,
                    token=token,
                    progress_callback=progress_callback
                )
            except Exception as e:
                print(f"hf_transfer repository download failed: {e}. Falling back to standard method.")
        
        # Async fallback method
        return await self._snapshot_download_fallback_async(repo_id, token, progress_callback)

    async def _snapshot_download_with_hf_transfer_progress_async(self, repo_id: str, token: str = None, progress_callback=None):
        """Async version of hf_transfer repository download with cancellation support"""
        import asyncio
        import time
                
        # Get session_id from progress_callback context if available
        session_id = getattr(progress_callback, 'session_id', None) if hasattr(progress_callback, 'session_id') else None
        
        # Properly handle token for subprocess script
        token_arg = f'"{token}"' if token else "None"
        
        download_script = f'''
import os
import sys
from huggingface_hub import snapshot_download

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

try:
    token_value = {token_arg}
    result = snapshot_download(
        repo_id="{repo_id}",
        token=token_value,
        local_dir_use_symlinks=False
    )
    print(f"DOWNLOAD_COMPLETE:{{result}}", flush=True)
except Exception as e:
    print(f"DOWNLOAD_ERROR:{{e}}", flush=True)
    sys.exit(1)
'''
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", download_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        downloaded_path = None
        
        async def monitor_download_progress():
            """Monitor download progress by checking file system"""
            nonlocal downloaded_path
            
            # Get the current event loop within the function
            loop = asyncio.get_event_loop()
            
            start_time = time.time()
            last_progress_time = start_time
            last_size = 0
            
            # Try to find the download directory by monitoring huggingface cache
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            
            # Look for the model directory pattern
            model_cache_pattern = f"models--{repo_id.replace('/', '--')}"
            
            while process.returncode is None:
                try:
                    # Check for cancellation
                    if session_id and download_cancellation_flags.get(session_id):
                        print("🚫 Repository download cancelled, terminating process")
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5.0)
                        except asyncio.TimeoutError:
                            process.kill()
                        raise asyncio.CancelledError("Download cancelled by user")
                    
                    current_time = time.time()
                    current_size = 0
                    
                    # Find and measure the download directory
                    if cache_dir.exists():
                        for item in cache_dir.iterdir():
                            if item.is_dir() and model_cache_pattern in item.name:
                                # Measure the size of this directory
                                current_size = await loop.run_in_executor(
                                    None, 
                                    lambda: self._get_directory_size(item)
                                )
                                break
                    
                    # Update progress if size changed significantly or enough time passed
                    if (current_size > last_size + 1024*1024 or  # Size increased by 1MB+
                        current_time - last_progress_time > 2.0):  # Or 2 seconds passed
                        
                        if progress_callback:
                            # Pass only current size, no total estimation
                            progress_callback(current_size, None)
                        
                        last_size = current_size
                        last_progress_time = current_time
                        
                        print(f"📊 Download progress: {self.utils.format_file_size(current_size)}")
                    
                    # Check for process completion every 0.5 seconds
                    await asyncio.sleep(0.5)
                    
                    # Safety timeout - if download takes too long, something might be wrong
                    if current_time - start_time > 1800:  # 30 minutes timeout
                        print("⚠️ Download timeout reached")
                        break
                        
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"⚠️ Error monitoring download progress: {e}")
                    await asyncio.sleep(1.0)
        
        async def read_process_output():
            """Read process output to get final download path"""
            nonlocal downloaded_path
            
            while True:
                try:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
                    if not line:
                        break
                        
                    line = line.decode().strip()
                    if not line:
                        continue
                        
                    print(f"Process output: {line}")
                    
                    if "DOWNLOAD_COMPLETE:" in line:
                        downloaded_path = line.split("DOWNLOAD_COMPLETE:", 1)[1]
                        print(f"📁 Download completed at: {downloaded_path}")
                        break
                    elif "DOWNLOAD_ERROR:" in line:
                        error_msg = line.split("DOWNLOAD_ERROR:", 1)[1]
                        raise Exception(f"Repository download failed: {error_msg}")
                        
                except asyncio.TimeoutError:
                    # Check if process is still running
                    if process.returncode is not None:
                        break
                    continue
                except Exception as e:
                    print(f"⚠️ Error reading process output: {e}")
                    break
        
        # Start both monitoring tasks
        progress_task = asyncio.create_task(monitor_download_progress())
        output_task = asyncio.create_task(read_process_output())
        
        try:
            # Wait for process to complete
            return_code = await process.wait()
            
            # Cancel monitoring tasks
            progress_task.cancel()
            output_task.cancel()
            
            # Wait for tasks to finish cancellation
            try:
                await asyncio.gather(progress_task, output_task, return_when=asyncio.ALL_COMPLETED)
            except asyncio.CancelledError:
                pass
            
            if return_code != 0:
                raise Exception(f"Repository download process failed with return code {return_code}")
            
            if not downloaded_path:
                raise Exception("Repository download completed but path not found")
            
            # Final progress update with actual final size
            if progress_callback:
                final_size = await loop.run_in_executor(
                    None, 
                    lambda: self._get_directory_size(Path(downloaded_path))
                )
                progress_callback(final_size, final_size)  # Signal completion
            
            # Cleanup symlinks after successful download
            result_path = Path(downloaded_path)
            cache_paths_to_cleanup = self.utils.resolve_all_symlinks_in_directory(result_path)
            self.utils.cleanup_cache_files(cache_paths_to_cleanup)
            
            return downloaded_path
            
        except asyncio.CancelledError:
            # Cancel monitoring tasks
            progress_task.cancel()
            output_task.cancel()
            
            # Ensure process is terminated
            if process.returncode is None:
                process.kill()
                try:
                    await process.wait()
                except:
                    pass
            
            print(f"Repository download cancelled")
            raise
        except Exception as e:
            # Cancel monitoring tasks
            progress_task.cancel()
            output_task.cancel()
            
            # Ensure process is terminated
            if process.returncode is None:
                process.kill()
                try:
                    await process.wait()
                except:
                    pass
            
            print(f"Repository download with progress failed: {e}")
            raise e

    def _get_directory_size(self, directory_path: Path) -> int:
        """Calculate total size of a directory recursively"""
        total_size = 0
        try:
            for item in directory_path.rglob('*'):
                if item.is_file():
                    try:
                        total_size += item.stat().st_size
                    except (OSError, FileNotFoundError):
                        # Skip files that can't be accessed
                        continue
        except Exception as e:
            print(f"Error calculating directory size for {directory_path}: {e}")
        return total_size

    async def _snapshot_download_fallback_async(self, repo_id: str, token: str = None, progress_callback=None):
        """Async fallback for repository download with file size monitoring"""
        import asyncio
        import time
        
        # Run the blocking operations in executor
        loop = asyncio.get_event_loop()
        
        # Progress tracking state
        download_completed = asyncio.Event()
        download_result = {"path": None, "error": None}
        
        async def progress_monitor():
            """Monitor download progress by checking cache directory size"""
            # Get the current event loop within the function
            current_loop = asyncio.get_event_loop()
            
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            model_cache_pattern = f"models--{repo_id.replace('/', '--')}"
            
            start_time = time.time()
            last_progress_time = start_time
            last_size = 0
            
            while not download_completed.is_set():
                try:
                    # Check for cancellation
                    if session_id and download_cancellation_flags.get(session_id):
                        print("🚫 Repository download cancelled, terminating task")
                        download_completed.set()
                        return
                    
                    current_time = time.time()
                    current_size = 0
                    
                    # Find and measure the download directory
                    if cache_dir.exists():
                        for item in cache_dir.iterdir():
                            if item.is_dir() and model_cache_pattern in item.name:
                                current_size = await current_loop.run_in_executor(
                                    None, 
                                    lambda: self._get_directory_size(item)
                                )
                                break
                    
                    # Update progress
                    if (current_size > last_size + 1024*1024 or 
                        current_time - last_progress_time > 2.0):
                        
                        if progress_callback:
                            # Pass only current size, no total estimation
                            progress_callback(current_size, None)
                        
                        last_size = current_size
                        last_progress_time = current_time
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    print(f"Error in progress monitor: {e}")
                    await asyncio.sleep(1.0)
        
        async def download_task():
            """Run the actual download"""
            try:
                result = await loop.run_in_executor(
                    None, 
                    lambda: snapshot_download(repo_id=repo_id, token=token, local_dir_use_symlinks=False)
                )
                download_result["path"] = result
            except Exception as e:
                download_result["error"] = e
            finally:
                download_completed.set()
        
        # Start monitoring and download tasks
        monitor_task = asyncio.create_task(progress_monitor())
        dl_task = asyncio.create_task(download_task())
        
        try:
            # Wait for download to complete
            await download_completed.wait()
            
            # Cancel monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
            
            # Check for errors
            if download_result["error"]:
                raise download_result["error"]
            
            result = download_result["path"]
            
            # Final progress update with actual final size
            if progress_callback:
                final_size = await loop.run_in_executor(
                    None, 
                    lambda: self._get_directory_size(Path(result))
                )
                progress_callback(final_size, final_size)  # Signal completion
            
            # Cleanup symlinks in executor
            result_path = Path(result)
            cache_paths_to_cleanup = await loop.run_in_executor(
                None, 
                lambda: self.utils.resolve_all_symlinks_in_directory(result_path)
            )
            await loop.run_in_executor(
                None, 
                lambda: self.utils.cleanup_cache_files(cache_paths_to_cleanup)
            )
            
            return result
            
        except Exception as e:
            # Cancel tasks
            monitor_task.cancel()
            dl_task.cancel()
            
            try:
                await asyncio.gather(monitor_task, dl_task, return_when=asyncio.ALL_COMPLETED)
            except asyncio.CancelledError:
                pass
            
            raise e

    def snapshot_download_with_progress(self, repo_id: str, token: str = None, progress_callback=None):
        """Synchronous wrapper for backward compatibility"""
        import asyncio
        
        # If we're already in an async context, create a new event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new thread with its own event loop
                import threading
                import concurrent.futures
                
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            self.snapshot_download_with_progress_async(repo_id, token, progress_callback)
                        )
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.snapshot_download_with_progress_async(repo_id, token, progress_callback)
                )
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(
                self.snapshot_download_with_progress_async(repo_id, token, progress_callback)
            )
