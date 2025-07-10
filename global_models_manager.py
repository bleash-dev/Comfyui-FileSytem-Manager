import os
import subprocess
import json
import asyncio
import time
from pathlib import Path
import folder_paths

# Add boto3 import
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("boto3 not available, falling back to AWS CLI")

# Import model config integration
try:
    from .model_config_integration import model_config_manager
    MODEL_CONFIG_AVAILABLE = True
except ImportError:
    print("Model config integration not available")
    MODEL_CONFIG_AVAILABLE = False

# Progress tracking for global model downloads
global_models_progress_store = {}

class GlobalModelsManager:
    def __init__(self):
        self.comfyui_base = Path(folder_paths.base_path)
        self.models_dir = self.comfyui_base / "models"
        self.bucket = os.environ.get('AWS_BUCKET_NAME')
        self.s3_models_base = f"s3://{self.bucket}/pod_sessions/global_shared/models/" if self.bucket else None
        
        # Initialize S3 client if boto3 is available
        self.s3_client = None
        if BOTO3_AVAILABLE and self.bucket:
            try:
                self.s3_client = boto3.client('s3')
                # Test credentials by listing bucket
                self.s3_client.head_bucket(Bucket=self.bucket)
                self.aws_configured = True
                print("✅ S3 client initialized successfully")
            except (ClientError, NoCredentialsError) as e:
                print(f"❌ S3 client initialization failed: {e}")
                self.s3_client = None
                self.aws_configured = self._check_aws_configuration()
        else:
            self.aws_configured = self._check_aws_configuration()
        
        # Add caching
        self.cache_file = self.comfyui_base / '.global_models_cache.json'
        self.cache_ttl = 300  # 5 minutes
        self._structure_cache = None
        self._cache_timestamp = 0
        
        # Track active downloads for cancellation
        self.active_downloads = {}

    def _check_aws_configuration(self):
        """Check if AWS CLI is configured"""
        try:
            result = subprocess.run(['aws', 's3', 'ls', self.s3_models_base], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False

    def _get_s3_model_size(self, s3_path):
        """Get model size from S3 using boto3 or AWS CLI"""
        if self.s3_client and s3_path.startswith("s3://"):
            try:
                parts = s3_path.replace("s3://", "").split('/', 1)
                if len(parts) >= 2:
                    bucket = parts[0]
                    key = parts[1]
                    response = self.s3_client.head_object(Bucket=bucket, Key=key)
                    return response.get('ContentLength')
            except Exception as e:
                print(f"Error getting S3 model size with boto3 for {s3_path}: {e}")
        
        # Fallback to AWS CLI
        if not self.aws_configured:
            return None
        try:
            if not s3_path.startswith("s3://"):
                return None
            parts = s3_path.replace("s3://", "").split('/', 1)
            if len(parts) < 2:
                return None
            bucket = parts[0]
            key = parts[1]
            command = ['aws', 's3api', 'head-object', '--bucket', bucket, '--key', key]
            success, output = self._run_aws_command(command)
            if success:
                data = json.loads(output)
                return data.get('ContentLength')
            return None
        except Exception as e:
            print(f"Error getting S3 model size for {s3_path}: {e}")
            return None

    def _run_aws_command(self, command, timeout=30):
        """Run AWS CLI command with error handling"""
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def _create_progress_callback(self, model_path, total_size):
        """Create a progress callback function for boto3 download"""
        downloaded = 0
        last_update = 0
        
        def progress_callback(chunk_size):
            nonlocal downloaded, last_update
            downloaded += chunk_size
            current_time = time.time()
            
            # Calculate progress percentage
            if total_size > 0:
                progress = min((downloaded / total_size) * 100, 100)
            else:
                # Fallback estimation
                progress = min((downloaded / (1024 * 1024 * 100)) * 100, 95)
            
            # Update progress store with formatted message
            if current_time - last_update >= 0.5:  # Update every 500ms
                if model_path in global_models_progress_store:
                    store_entry = global_models_progress_store[model_path]
                    if store_entry.get("status") == "downloading":
                        # Format the complete message on the backend
                        downloaded_formatted = self._format_file_size(downloaded)
                        total_formatted = self._format_file_size(total_size) if total_size > 0 else "Unknown"
                        
                        if total_size > 0:
                            message = f"📥 {downloaded_formatted} / {total_formatted} ({int(progress)}%)"
                        else:
                            message = f"📥 {downloaded_formatted} downloaded ({int(progress)}%)"
                        
                        store_entry["progress"] = progress
                        store_entry["downloaded_size"] = downloaded
                        store_entry["total_size"] = total_size
                        store_entry["message"] = message  # Add formatted message
                        last_update = current_time
                        
                        # Log progress for debugging (every 10% to reduce spam)
                        if int(progress) % 10 == 0 and progress > 0:
                            print(f"📥 Download progress for {model_path}: {progress:.1f}% ({downloaded}/{total_size} bytes)")
        
        return progress_callback

    def _format_file_size(self, bytes_size):
        """Format file size in human readable format"""
        if bytes_size == 0:
            return '0 B'
        
        k = 1024
        sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        i = int(len(sizes) - 1) if bytes_size >= k ** (len(sizes) - 1) else int(
            __import__('math').log(bytes_size) / __import__('math').log(k)
        )
        
        return f"{bytes_size / (k ** i):.1f} {sizes[i]}"

    async def download_model(self, model_path):
        """Download a specific model from global storage with real-time progress"""
        if not self.aws_configured or not self.s3_models_base:
            global_models_progress_store[model_path] = {
                "progress": 0, 
                "status": "failed", 
                "message": "❌ AWS not configured"
            }
            return False
        
        try:
            # Clean up any existing progress/cancellation state for retry
            if model_path in self.active_downloads:
                del self.active_downloads[model_path]
            
            # Clear any existing progress entry to start fresh
            if model_path in global_models_progress_store:
                # Keep only essential info if restarting
                old_entry = global_models_progress_store[model_path]
                if old_entry.get("status") in ["cancelled", "failed"]:
                    print(f"🔄 Retrying download for {model_path}")
            
            path_parts = model_path.split('/')
            if len(path_parts) < 2:
                global_models_progress_store[model_path] = {
                    "progress": 0, 
                    "status": "failed", 
                    "message": "❌ Invalid model path"
                }
                return False
            
            category = path_parts[0]
            filename = '/'.join(path_parts[1:])
            
            s3_full_path = f"{self.s3_models_base}{category}/{filename}"
            local_path = self.models_dir / category / filename
            
            # Clean up any partial download files for retry
            if local_path.exists():
                try:
                    local_path.unlink()
                    print(f"🧹 Cleaned up partial download: {local_path}")
                except OSError as e:
                    print(f"Warning: Could not clean up partial download {local_path}: {e}")
            
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Get file size from S3 for progress tracking
            total_size = self._get_s3_model_size(s3_full_path)
            if not total_size:
                print(f"Warning: Could not determine file size for {model_path}, progress may be inaccurate")
                total_size = 0
            
            # Initialize progress tracking with formatted message
            global_models_progress_store[model_path] = {
                "progress": 0, 
                "status": "downloading",
                "total_size": total_size,
                "downloaded_size": 0,
                "message": "🚀 Starting download..."
            }

            # Mark this download as active for cancellation tracking
            self.active_downloads[model_path] = {"cancelled": False}

            print(f"🚀 Starting download: {model_path} ({total_size} bytes)")

            # Use boto3 if available for better progress tracking
            if self.s3_client and s3_full_path.startswith("s3://"):
                success = await self._download_with_boto3(model_path, s3_full_path, local_path, total_size)
            else:
                # Fallback to AWS CLI with monitoring
                success = await self._download_with_aws_cli(model_path, s3_full_path, local_path, total_size)

            # Check for final cancellation
            if self.active_downloads.get(model_path, {}).get("cancelled"):
                if local_path.exists():
                    try:
                        local_path.unlink()
                        print(f"🗑️ Removed cancelled download: {local_path}")
                    except OSError as e:
                        print(f"Error removing cancelled download {local_path}: {e}")
                
                global_models_progress_store[model_path] = {
                    "progress": 0,
                    "status": "cancelled",
                    "total_size": total_size,
                    "downloaded_size": 0
                }
                return False

            if success:
                # Get final file size
                final_size = 0
                if local_path.exists():
                    final_size = local_path.stat().st_size
                    print(f"✅ Download complete: {model_path} ({final_size} bytes)")
                
                # Register the model with the configuration manager
                if MODEL_CONFIG_AVAILABLE:
                    try:
                        model_config_manager.register_s3_model(
                            local_path=str(local_path),
                            s3_path=s3_full_path,
                            model_name=filename,
                            model_type=category
                        )
                        print(f"📝 Model registered in config: {model_path}")
                    except Exception as e:
                        print(f"⚠️ Failed to register model in config: {e}")
                
                # Mark as completed with success message
                global_models_progress_store[model_path] = {
                    "progress": 100, 
                    "status": "downloaded",
                    "total_size": total_size or final_size,
                    "downloaded_size": final_size,
                    "message": "✅ Download complete!"
                }
                return True
            else:
                print(f"❌ Download failed: {model_path}")
                global_models_progress_store[model_path] = {
                    "progress": 0, 
                    "status": "failed", 
                    "total_size": total_size,
                    "downloaded_size": 0,
                    "message": "❌ Download failed"
                }
                
                # Clean up failed download
                if local_path.exists():
                    try:
                        local_path.unlink()
                        print(f"🗑️ Removed failed download: {local_path}")
                    except OSError as e:
                        print(f"Error cleaning up failed download {local_path}: {e}")
                return False
                
        except Exception as e:
            print(f"💥 Error downloading model {model_path}: {e}")
            global_models_progress_store[model_path] = {
                "progress": 0, 
                "status": "failed", 
                "total_size": 0,
                "downloaded_size": 0,
                "message": f"❌ Error: {str(e)} - Click retry to try again"
            }
            return False
        finally:
            # Clean up active download tracking
            if model_path in self.active_downloads:
                del self.active_downloads[model_path]

    async def _download_with_boto3(self, model_path, s3_full_path, local_path, total_size):
        """Download using boto3 with real-time progress callbacks"""
        try:
            # Parse S3 path
            parts = s3_full_path.replace("s3://", "").split('/', 1)
            if len(parts) < 2:
                return False
            
            bucket = parts[0]
            key = parts[1]
            
            # Create progress callback
            progress_callback = self._create_progress_callback(model_path, total_size)
            
            # Create async wrapper for download
            def do_download():
                try:
                    with open(local_path, 'wb') as f:
                        self.s3_client.download_fileobj(
                            bucket, key, f, 
                            Callback=progress_callback
                        )
                    return True
                except Exception as e:
                    print(f"Boto3 download error: {e}")
                    return False
            
            # Run download in executor with cancellation support
            loop = asyncio.get_event_loop()
            download_task = loop.run_in_executor(None, do_download)
            
            # Monitor for cancellation
            while not download_task.done():
                await asyncio.sleep(0.1)
                
                # Check for cancellation
                if self.active_downloads.get(model_path, {}).get("cancelled"):
                    print(f"🚫 Cancelling boto3 download for {model_path}")
                    download_task.cancel()
                    return False
            
            # Get result
            try:
                return await download_task
            except asyncio.CancelledError:
                return False
                
        except Exception as e:
            print(f"Error in boto3 download: {e}")
            return False

    async def _download_with_aws_cli(self, model_path, s3_full_path, local_path, total_size):
        """Fallback download using AWS CLI with file size monitoring"""
        try:
            command = ['aws', 's3', 'cp', s3_full_path, str(local_path)]
            print(f"📥 Using AWS CLI: {' '.join(command)}")

            # Create async wrapper for AWS CLI
            async def do_download():
                loop = asyncio.get_event_loop()
                try:
                    return await loop.run_in_executor(None, lambda: self._run_aws_command(command, timeout=600))
                except Exception as e:
                    print(f"AWS CLI download error: {e}")
                    return False, str(e)

            # Start download and monitoring
            download_task = asyncio.create_task(do_download())
            monitor_task = asyncio.create_task(self._monitor_progress(model_path, local_path, total_size))

            # Wait for download with cancellation support
            while not download_task.done():
                await asyncio.sleep(0.5)
                
                # Check for cancellation
                if self.active_downloads.get(model_path, {}).get("cancelled"):
                    print(f"🚫 Cancelling AWS CLI download for {model_path}")
                    download_task.cancel()
                    monitor_task.cancel()
                    return False
            
            # Stop monitoring
            monitor_task.cancel()
            
            # Get result
            try:
                success, output = await download_task
                return success
            except asyncio.CancelledError:
                return False
                
        except Exception as e:
            print(f"Error in AWS CLI download: {e}")
            return False

    async def _monitor_progress(self, model_path, local_path, total_size):
        """Monitor download progress by watching file size changes (fallback for AWS CLI)"""
        if not total_size or total_size == 0:
            total_size = 1024 * 1024 * 100  # Assume 100MB as default
        
        last_size = 0
        stalled_count = 0
        max_stalled_iterations = 60
        
        while True:
            try:
                # Check for cancellation
                if self.active_downloads.get(model_path, {}).get("cancelled"):
                    break
                
                current_size = 0
                if local_path.exists():
                    current_size = local_path.stat().st_size
                
                # Calculate progress percentage
                if total_size > 0:
                    progress = min((current_size / total_size) * 100, 100)
                else:
                    progress = min((current_size / (1024 * 1024 * 100)) * 100, 95)
                
                # Update progress store with formatted message
                if model_path in global_models_progress_store:
                    store_entry = global_models_progress_store[model_path]
                    if store_entry.get("status") == "downloading":
                        # Format the complete message on the backend
                        downloaded_formatted = self._format_file_size(current_size)
                        total_formatted = self._format_file_size(total_size) if total_size > 0 else "Unknown"
                        
                        if total_size > 0:
                            message = f"📥 {downloaded_formatted} / {total_formatted} ({int(progress)}%)"
                        else:
                            message = f"📥 {downloaded_formatted} downloaded ({int(progress)}%)"
                        
                        store_entry["progress"] = progress
                        store_entry["downloaded_size"] = current_size
                        store_entry["total_size"] = total_size
                        store_entry["message"] = message
                
                # Check if download is stalled
                if current_size == last_size:
                    stalled_count += 1
                    if stalled_count >= max_stalled_iterations:
                        print(f"⚠️ Download stalled for {model_path}")
                        # Update message to show stalled status
                        if model_path in global_models_progress_store:
                            global_models_progress_store[model_path]["message"] = "⚠️ Download stalled..."
                else:
                    stalled_count = 0
                
                last_size = current_size
                
                # If we've reached completion
                if progress >= 99.9 or (total_size > 0 and current_size >= total_size):
                    if model_path in global_models_progress_store:
                        global_models_progress_store[model_path]["message"] = "🔄 Finishing download..."
                    break
                    
            except Exception as e:
                print(f"Error monitoring progress for {model_path}: {e}")
                if model_path in global_models_progress_store:
                    global_models_progress_store[model_path]["message"] = f"❌ Monitor error: {str(e)}"
                break
            
            await asyncio.sleep(0.5)  # Check every 500ms

    async def cancel_download(self, model_path):
        """Cancel an active download"""
        if model_path in self.active_downloads:
            print(f"🚫 Cancelling download for {model_path}")
            self.active_downloads[model_path]["cancelled"] = True
            
            # Update progress store with cancellation message
            if model_path in global_models_progress_store:
                global_models_progress_store[model_path]["status"] = "cancelled"
                global_models_progress_store[model_path]["message"] = "🚫 Download cancelled - Click retry to restart"
            
            return True
        return False

    async def get_global_models_structure(self, force_refresh=False):
        """Get the structure of available global models from S3 with caching"""
        if not self.aws_configured or not self.s3_models_base:
            print("AWS not configured or S3 base path not set.")
            return {}
        
        # Check cache first
        current_time = time.time()
        if (not force_refresh and 
            self._structure_cache and 
            (current_time - self._cache_timestamp) < self.cache_ttl):
            return self._structure_cache
        
        # Try to load from disk cache
        if not force_refresh and self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    if (current_time - cache_data.get('timestamp', 0)) < self.cache_ttl:
                        self._structure_cache = cache_data.get('structure', {})
                        self._cache_timestamp = cache_data.get('timestamp', 0)
                        return self._structure_cache
            except Exception as e:
                print(f"Error loading cache: {e}")
        
        try:
            command = ['aws', 's3', 'ls', self.s3_models_base, '--recursive']
            success, output = self._run_aws_command(command, timeout=60)
            
            if not success:
                print(f"Failed to list S3 models: {output}")
                return self._structure_cache or {}
            
            structure = {}
            for line in output.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        size = int(parts[2]) if parts[2].isdigit() else 0
                        full_path = ' '.join(parts[3:])
                        
                        # Remove the base path to get relative path
                        if full_path.startswith('pod_sessions/global_shared/models/'):
                            relative_path = full_path.replace('pod_sessions/global_shared/models/', '')
                            
                            # Split path into components
                            path_components = relative_path.split('/')
                            
                            # Navigate/create nested structure
                            current_level = structure
                            
                            # Process all path components except the last one (which is the file)
                            for i, component in enumerate(path_components[:-1]):
                                if component not in current_level:
                                    current_level[component] = {}
                                current_level = current_level[component]
                            
                            # Add the file at the final level
                            if len(path_components) >= 1:
                                filename = path_components[-1]
                                # Skip empty filenames and validate
                                if not filename or not filename.strip() or filename == '':
                                    print(f"Skipping empty filename in path: {relative_path}")
                                    continue
                                
                                # Skip system files and hidden files that shouldn't be downloadable
                                if filename.startswith('.') and filename not in ['.gitkeep']:
                                    print(f"Skipping hidden/system file: {filename}")
                                    continue
                                    
                                current_level[filename] = {
                                    'type': 'file',
                                    'size': size,
                                    's3_path': full_path,
                                    'local_path': str(self.models_dir / relative_path)
                                }
            
            # Update cache
            self._structure_cache = structure
            self._cache_timestamp = current_time
            
            # Save to disk cache
            try:
                cache_data = {
                    'structure': structure,
                    'timestamp': current_time
                }
                with open(self.cache_file, 'w') as f:
                    json.dump(cache_data, f)
            except Exception as e:
                print(f"Error saving cache: {e}")
            
            return structure
            
        except Exception as e:
            print(f"Error getting global models structure: {e}")
            return self._structure_cache or {}

    async def upload_model(self, local_path):
        """Upload a model to global storage"""
        if not self.aws_configured or not self.s3_models_base:
            return False
        
        try:
            local_path = Path(local_path)
            if not local_path.exists():
                return False
            
            # Get relative path within models directory
            relative_path = local_path.relative_to(self.models_dir)
            s3_path = f"{self.s3_models_base}{relative_path}"
            
            command = ['aws', 's3', 'cp', str(local_path), s3_path]
            success, output = self._run_aws_command(command, timeout=600)  # 10 minute timeout
            
            if success:
                print(f"Successfully uploaded {local_path} to {s3_path}")
                return True
            else:
                print(f"Failed to upload {local_path}: {output}")
                return False
                
        except Exception as e:
            print(f"Error uploading model {local_path}: {e}")
            return False

    def check_model_exists_locally(self, model_path):
        """Check if a model exists locally"""
        try:
            local_path = self.models_dir / model_path
            return local_path.exists()
        except Exception:
            return False

    def get_model_status(self, model_path):
        """Get status of a model (local, available, downloading, etc.)"""
        local_exists = self.check_model_exists_locally(model_path)
        
        # Check if model is available in global storage
        # This would need to be cached or optimized for large numbers of models
        
        if local_exists:
            return "downloaded"
        else:
            return "available"  # Simplified - would need actual S3 check

    async def sync_all_models(self):
        """Sync all global models to local storage"""
        if not self.aws_configured or not self.s3_models_base:
            return False
        
        try:
            command = ['aws', 's3', 'sync', self.s3_models_base, str(self.models_dir)]
            success, output = self._run_aws_command(command, timeout=1800)  # 30 minute timeout
            
            if success:
                print("Successfully synced all global models")
                return True
            else:
                print(f"Failed to sync global models: {output}")
                return False
                
        except Exception as e:
            print(f"Error syncing all models: {e}")
            return False

    def get_s3_connectivity_status(self):
        """Check S3 connectivity for global models"""
        if not self.aws_configured:
            return {"connected": False, "error": "AWS CLI not configured"}
        
        if not self.bucket:
            return {"connected": False, "error": "AWS_BUCKET_NAME not set"}
        
        try:
            command = ['aws', 's3', 'ls', f"s3://{self.bucket}/"]
            success, output = self._run_aws_command(command, timeout=10)
            
            return {
                "connected": success,
                "error": output if not success else None,
                "bucket": self.bucket,
                "models_path": self.s3_models_base
            }
            
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    def _get_directory_structure(self, directory):
        """Recursively get directory structure"""
        items = {}
        
        for item in directory.iterdir():
            if item.name.startswith('.'):
                continue
                
            if item.is_file():
                items[item.name] = {
                    'type': 'file',
                    'size': item.stat().st_size,
                    'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                    'local_path': str(item),
                    'local_exists': True,
                    'download_progress': 100
                }
            elif item.is_dir():
                items[item.name] = {
                    'type': 'directory',
                    'items': self._get_directory_structure(item),
                    'local_exists': True
                }
        
        return {
            'type': 'directory',
            'items': items,
            'local_exists': True
        }
    
    def get_enhanced_directory_contents(self, category_path):
        """Get directory contents enhanced with global model information"""
        local_path = self.models_dir / category_path if category_path else self.models_dir
        contents = []
        
        # Get local items
        local_items = {}
        if local_path.exists() and local_path.is_dir():
            for item in local_path.iterdir():
                if item.name.startswith('.'):
                    continue
                
                relative_path = str(item.relative_to(self.models_dir))
                local_items[item.name] = {
                    "name": item.name,
                    "path": relative_path,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                    "modified": item.stat().st_mtime,
                    "local_exists": True,
                    "global_exists": False,
                    "downloadable": False
                }
        
        # Add global models if we're in the models directory or a category
        try:
            import asyncio
            
            # Get cached global structure (don't force refresh for directory browsing)
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    global_structure = cache_data.get('structure', {})
                    
                    if not category_path:
                        # We're in the root models directory - show categories
                        for category_name, category_data in global_structure.items():
                            if category_name not in local_items:
                                local_items[category_name] = {
                                    "name": category_name,
                                    "path": category_name,
                                    "type": "directory",
                                    "size": 0,
                                    "modified": 0,
                                    "local_exists": False,
                                    "global_exists": True,
                                    "downloadable": False
                                }
                            else:
                                local_items[category_name]["global_exists"] = True
                    
                    else:
                        # We're in a specific category - show models
                        category_name = category_path.split('/')[0]
                        if category_name in global_structure:
                            for model_name, model_data in global_structure[category_name].items():
                                relative_path = f"{category_name}/{model_name}"
                                if model_name not in local_items:
                                    local_items[model_name] = {
                                        "name": model_name,
                                        "path": relative_path,
                                        "type": model_data["type"],
                                        "size": model_data.get("size", 0),
                                        "modified": 0,
                                        "local_exists": False,
                                        "global_exists": True,
                                        "downloadable": True,
                                        "s3_path": model_data["s3_path"]
                                    }
                                else:
                                    local_items[model_name]["global_exists"] = True
                                    local_items[model_name]["downloadable"] = True
                                    local_items[model_name]["s3_path"] = model_data["s3_path"]
        
        except Exception as e:
            print(f"Error adding global models info: {e}")
        
        return list(local_items.values())

