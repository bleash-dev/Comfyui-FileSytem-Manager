import os
import subprocess
import json
import asyncio
import time
from pathlib import Path
import folder_paths

# Progress tracking for global model downloads
global_models_progress_store = {}

class GlobalModelsManager:
    def __init__(self):
        self.comfyui_base = Path(folder_paths.base_path)
        self.models_dir = self.comfyui_base / "models"
        self.bucket = os.environ.get('AWS_BUCKET_NAME')
        self.s3_models_base = f"s3://{self.bucket}/pod_sessions/global_shared/models/" if self.bucket else None
        self.aws_configured = self._check_aws_configuration()
        
        # Add caching
        self.cache_file = self.comfyui_base / '.global_models_cache.json'
        self.cache_ttl = 300  # 5 minutes
        self._structure_cache = None
        self._cache_timestamp = 0
        
    def _check_aws_configuration(self):
        """Check if AWS CLI is configured"""
        try:
            result = subprocess.run(['aws', 's3', 'ls', self.s3_models_base], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False

    def _get_s3_model_size(self, s3_path):
        """Get model size from S3 using aws s3api head-object"""
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

    async def _monitor_progress(self, model_path, local_path, total_size):
        """Monitor download progress of a file by watching file size changes."""
        if not total_size or total_size == 0:
            # If we don't know the total size, we'll estimate based on file growth
            total_size = 1024 * 1024 * 100  # Assume 100MB as default
        
        store_entry = global_models_progress_store.get(model_path)
        if not store_entry:
            return

        last_size = 0
        stalled_count = 0
        max_stalled_iterations = 30  # 30 seconds of no progress before considering stalled
        
        while store_entry.get("status") == "downloading":
            try:
                current_size = 0
                if local_path.exists():
                    current_size = local_path.stat().st_size
                
                # Calculate progress percentage
                if total_size > 0:
                    progress = min((current_size / total_size) * 100, 100)
                else:
                    # Fallback: estimate progress based on file size growth
                    progress = min((current_size / (1024 * 1024 * 100)) * 100, 95)  # Cap at 95% for unknown size
                
                # Update progress store
                store_entry["progress"] = progress
                store_entry["downloaded_size"] = current_size
                store_entry["total_size"] = total_size
                
                # Check if download is stalled
                if current_size == last_size:
                    stalled_count += 1
                    if stalled_count >= max_stalled_iterations:
                        print(f"Download appears stalled for {model_path}. No progress for {max_stalled_iterations} seconds.")
                        # Don't break here, let the main download process handle timeouts
                else:
                    stalled_count = 0  # Reset stall counter
                
                last_size = current_size
                
                # If we've reached 100% or the expected file size, we're likely done
                if progress >= 99.9 or (total_size > 0 and current_size >= total_size):
                    print(f"Download monitoring complete for {model_path}: {current_size}/{total_size} bytes")
                    break
                    
                # Log progress every 10% for debugging
                if int(progress) % 10 == 0 and progress > 0:
                    print(f"Download progress for {model_path}: {progress:.1f}% ({current_size}/{total_size} bytes)")
                
            except Exception as e:
                print(f"Error monitoring progress for {model_path}: {e}")
                break
            
            # Check for cancellation
            if store_entry.get("status") == "cancelled":
                print(f"Download monitoring cancelled for {model_path}")
                break
                
            await asyncio.sleep(1)  # Check every second

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

    async def download_model(self, model_path):
        """Download a specific model from global storage"""
        if not self.aws_configured or not self.s3_models_base:
            global_models_progress_store[model_path] = {"progress": 0, "status": "failed", "error": "AWS not configured"}
            return False
        
        try:
            path_parts = model_path.split('/')
            if len(path_parts) < 2:
                global_models_progress_store[model_path] = {"progress": 0, "status": "failed", "error": "Invalid model path"}
                return False
            
            category = path_parts[0]
            filename = '/'.join(path_parts[1:])
            
            s3_full_path = f"{self.s3_models_base}{category}/{filename}"
            local_path = self.models_dir / category / filename
            
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Get file size from S3 for progress tracking
            total_size = self._get_s3_model_size(s3_full_path)
            if not total_size:
                print(f"Warning: Could not determine file size for {model_path}, progress may be inaccurate")
                total_size = 0
            
            # Initialize progress tracking
            global_models_progress_store[model_path] = {
                "progress": 0, 
                "status": "downloading",
                "total_size": total_size,
                "downloaded_size": 0
            }

            command = ['aws', 's3', 'cp', s3_full_path, str(local_path)]
            print(f"Starting download: {' '.join(command)}")

            # Create a proper async wrapper for the synchronous download
            async def do_download():
                loop = asyncio.get_event_loop()
                try:
                    return await loop.run_in_executor(None, lambda: self._run_aws_command(command, timeout=600))
                except Exception as e:
                    print(f"Download execution error: {e}")
                    return False, str(e)

            # Start the download task
            download_task = asyncio.create_task(do_download())
            
            # Start progress monitoring immediately
            progress_task = asyncio.create_task(self._monitor_progress(model_path, local_path, total_size))

            # Monitor both download completion and cancellation
            while not download_task.done():
                await asyncio.sleep(0.5)
                
                # Check for cancellation
                current_entry = global_models_progress_store.get(model_path, {})
                if current_entry.get("status") == "cancelled":
                    print(f"Cancelling download for {model_path}")
                    
                    # Cancel both tasks
                    download_task.cancel()
                    progress_task.cancel()
                    
                    # Clean up any partially downloaded file
                    if local_path.exists():
                        try:
                            local_path.unlink()
                            print(f"Removed partially downloaded file after cancellation: {local_path}")
                        except OSError as e:
                            print(f"Error removing partial download {local_path}: {e}")
                    return False
            
            # Get download result
            try:
                success, output = await download_task
            except asyncio.CancelledError:
                print(f"Download task cancelled for {model_path}")
                return False
            
            # Final cancellation check
            current_entry = global_models_progress_store.get(model_path, {})
            if current_entry.get("status") == "cancelled":
                if local_path.exists():
                    try:
                        local_path.unlink()
                        print(f"Removed downloaded file after cancellation: {local_path}")
                    except OSError as e:
                        print(f"Error removing download {local_path}: {e}")
                return False
            
            # Update status to finishing and stop progress monitoring
            if model_path in global_models_progress_store:
                global_models_progress_store[model_path]["status"] = "finishing"
            
            # Wait for progress monitoring to complete
            try:
                await progress_task
            except asyncio.CancelledError:
                pass  # Progress task was cancelled, that's fine

            if success:
                print(f"Successfully downloaded {model_path} to {local_path}")
                
                # Get final file size
                final_size = 0
                if local_path.exists():
                    final_size = local_path.stat().st_size
                    print(f"Final file size: {final_size} bytes")
                
                # Mark as completed
                global_models_progress_store[model_path] = {
                    "progress": 100, 
                    "status": "downloaded",
                    "total_size": total_size or final_size,
                    "downloaded_size": final_size
                }
                return True
            else:
                print(f"Failed to download {model_path}: {output}")
                global_models_progress_store[model_path] = {
                    "progress": 0, 
                    "status": "failed", 
                    "error": output,
                    "total_size": total_size,
                    "downloaded_size": 0
                }
                
                # Clean up failed download
                if local_path.exists():
                    try:
                        local_path.unlink()
                        print(f"Removed failed download file: {local_path}")
                    except OSError as e:
                        print(f"Error cleaning up failed download {local_path}: {e}")
                return False
                
        except Exception as e:
            print(f"Error downloading model {model_path}: {e}")
            global_models_progress_store[model_path] = {
                "progress": 0, 
                "status": "failed", 
                "error": str(e),
                "total_size": 0,
                "downloaded_size": 0
            }
            return False

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

