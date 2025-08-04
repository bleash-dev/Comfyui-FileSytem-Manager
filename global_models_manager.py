import os
import json
import time
import tempfile
import tarfile
import subprocess
from pathlib import Path
from datetime import datetime
import folder_paths

# Import centralized S3 client
try:
    from .s3_client import get_s3_client, S3ClientConfig
    S3_CLIENT_AVAILABLE = True
except ImportError:
    print("S3 client not available")
    S3_CLIENT_AVAILABLE = False
    get_s3_client = None
    S3ClientConfig = None

# Removed legacy boto3 import - using centralized S3 client only

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
        self.s3_models_base = (
            f"s3://{self.bucket}/pod_sessions/global_shared/models/"
            if self.bucket else None
        )
        
        # Initialize centralized S3 client
        self.s3_client = None
        self.aws_configured = False
        
        if S3_CLIENT_AVAILABLE:
            try:
                self.s3_client = get_s3_client()
                self.aws_configured = self.s3_client.is_connected
                if self.aws_configured:
                    provider = self.s3_client.config.provider
                    print(f"✅ Using centralized S3 client (Provider: {provider})")
                else:
                    error = self.s3_client.connection_error
                    print(f"❌ S3 client not connected: {error}")
            except Exception as e:
                print(f"❌ Error initializing S3 client: {e}")
                self.s3_client = None
        else:
            print("❌ S3 client not available")
        
        # Add caching
        self.cache_file = self.comfyui_base / '.global_models_cache.json'
        self.cache_ttl = 300  # 5 minutes
        self._structure_cache = None
        self._cache_timestamp = 0
        
        # Track active downloads for cancellation
        self.active_downloads = {}

    async def get_s3_model_size(self, model_path):
        """Get model size from S3 using centralized S3 client"""
        if not self.s3_client or not self.aws_configured:
            return None
        
        try:
            # Use the centralized client to get object size
            return await self.s3_client.get_object_size(model_path)
        except Exception as e:
            print(f"Error getting S3 model size for {model_path}: {e}")
            return None

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

    def cleanup_temp_file(self, temp_path):
        """Clean up temporary file safely"""
        try:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
                print(f"🗑️ Cleaned up temp file: {temp_path}")
        except Exception as e:
            print(f"⚠️ Failed to clean up temp file {temp_path}: {e}")

    def move_temp_to_final(self, temp_path, final_path, session_id=None):
        """Move temporary file to final destination with cancellation check"""
        try:
            # Check for cancellation before moving
            if session_id and self.active_downloads.get(session_id, {}).get("cancelled"):
                self.cleanup_temp_file(temp_path)
                return False
            
            temp_file = Path(temp_path)
            final_file = Path(final_path)
            
            # Ensure target directory exists
            final_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file atomically
            temp_file.rename(final_file)
            return True
            
        except Exception as e:
            self.cleanup_temp_file(temp_path)
            raise e

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
        if not self.s3_client or not self.aws_configured:
            global_models_progress_store[model_path] = {
                "progress": 0,
                "status": "failed",
                "message": "❌ S3 client not configured"
            }
            return False

        try:
            # Clean up any existing progress/cancellation state for retry
            if model_path in self.active_downloads:
                del self.active_downloads[model_path]

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

            # Use the S3 key format expected by the centralized client
            s3_key = f"pod_sessions/global_shared/models/{category}/{filename}"
            local_path = self.models_dir / category / filename

            # Create temporary file for download in /tmp
            temp_dir = Path(tempfile.gettempdir())
            temp_download_path = temp_dir / f"s3_model_{model_path.replace('/', '_')}.tmp"

            # Clean up any existing temp file for retry
            if temp_download_path.exists():
                try:
                    temp_download_path.unlink()
                    print(f"🧹 Cleaned up existing temp file: {temp_download_path}")
                except OSError as e:
                    print(f"Warning: Could not clean up temp file {temp_download_path}: {e}")

            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Get compression info from global structure cache
            is_compressed = False
            actual_s3_key = s3_key
            compressed_size = 0
            
            # Check cached structure for compression info
            if self._structure_cache:
                # Navigate through the structure to find file info
                try:
                    current_level = self._structure_cache
                    for part in path_parts[:-1]:  # Navigate to category
                        current_level = current_level.get(part, {})
                    
                    # Get file info
                    file_info = current_level.get(filename, {})
                    if isinstance(file_info, dict) and file_info.get('type') == 'file':
                        is_compressed = file_info.get('compressed', False)
                        if is_compressed:
                            actual_s3_key = file_info.get('s3_path', s3_key)
                            compressed_size = file_info.get('compressed_size', 0)
                            print(f"🗜️ Using compressed version: {actual_s3_key}")
                        total_size = file_info.get('size', 0)  # Uncompressed size
                    else:
                        # Fallback to checking S3 directly
                        total_size = await self.get_s3_model_size(s3_key)
                except Exception as e:
                    print(f"Warning: Error checking cache for compression info: {e}")
                    total_size = await self.get_s3_model_size(s3_key)
            else:
                # No cache - try to detect compression by checking for both formats
                compressed_s3_key_zstd = f"{s3_key}.tar.zstd"
                compressed_s3_key_zst = f"{s3_key}.tar.zst"
                
                compressed_size = await self.get_s3_model_size(compressed_s3_key_zstd)
                if compressed_size and compressed_size > 0:
                    print(f"🗜️ Compressed version detected: {compressed_s3_key_zstd}")
                    actual_s3_key = compressed_s3_key_zstd
                    is_compressed = True
                    total_size = compressed_size  # Will show compressed size in progress
                else:
                    # Try .tar.zst format
                    compressed_size = await self.get_s3_model_size(compressed_s3_key_zst)
                    if compressed_size and compressed_size > 0:
                        print(f"🗜️ Compressed version detected: {compressed_s3_key_zst}")
                        actual_s3_key = compressed_s3_key_zst
                        is_compressed = True
                        total_size = compressed_size  # Will show compressed size in progress
                    else:
                        # Fallback to uncompressed version
                        total_size = await self.get_s3_model_size(s3_key)
            
            if not total_size:
                print(f"Warning: Could not determine file size for {model_path}")
                total_size = 0

            # Initialize progress tracking
            global_models_progress_store[model_path] = {
                "progress": 0,
                "status": "downloading",
                "total_size": total_size,
                "downloaded_size": 0,
                "message": "🚀 Starting download..."
            }

            # Mark this download as active for cancellation tracking
            self.active_downloads[model_path] = {
                "cancelled": False,
                "local_path": str(local_path),
                "expected_size": total_size
            }

            print(f"🚀 Starting download: {model_path} ({total_size} bytes)")

            # Create progress callback for centralized client
            def progress_callback(downloaded_size, total_file_size,
                                  progress_percent):
                if model_path not in global_models_progress_store:
                    return

                # Check for cancellation
                if self.active_downloads.get(model_path, {}).get("cancelled"):
                    return

                downloaded_formatted = self._format_file_size(downloaded_size)
                total_formatted = (self._format_file_size(total_file_size)
                                   if total_file_size > 0 else "Unknown")

                if total_file_size > 0:
                    message = (f"📥 {downloaded_formatted} / {total_formatted} "
                               f"({progress_percent:.1f}%)")
                else:
                    message = f"📥 {downloaded_formatted} downloaded"

                global_models_progress_store[model_path].update({
                    "progress": progress_percent,
                    "downloaded_size": downloaded_size,
                    "total_size": total_file_size,
                    "message": message
                })

            print(f"📥 Using centralized S3 client: s3 download {actual_s3_key}")

            # Download using centralized S3 client
            success = await self.s3_client.download_file(
                actual_s3_key, temp_download_path, progress_callback=progress_callback
            )

            # Check for final cancellation
            if self.active_downloads.get(model_path, {}).get("cancelled"):
                # Clean up temp file
                if temp_download_path.exists():
                    try:
                        temp_download_path.unlink()
                        print(f"🗑️ Removed cancelled temp file: {temp_download_path}")
                    except OSError as e:
                        print(f"Error removing cancelled temp file {temp_download_path}: {e}")

                global_models_progress_store[model_path] = {
                    "progress": 0,
                    "status": "cancelled",
                    "total_size": total_size,
                    "downloaded_size": 0
                }
                return False

            if success:
                # Check for cancellation before processing file
                if self.active_downloads.get(model_path, {}).get("cancelled"):
                    # Clean up temp file
                    if temp_download_path.exists():
                        temp_download_path.unlink()
                    return False

                # Handle decompression if needed
                final_temp_path = temp_download_path
                if is_compressed:
                    print(f"🗜️ Decompressing {temp_download_path.name}...")
                    
                    # Update progress to show decompression
                    global_models_progress_store[model_path].update({
                        "message": "🗜️ Decompressing..."
                    })
                    
                    # Create temp path for decompressed file
                    decompressed_temp = temp_dir / (
                        f"s3_model_{model_path.replace('/', '_')}_decompressed.tmp"
                    )
                    
                    # Decompress the file
                    decompress_success = await self._decompress_file(
                        str(temp_download_path), str(decompressed_temp)
                    )
                    
                    if not decompress_success:
                        print(f"❌ Decompression failed for {model_path}")
                        # Clean up temp files
                        self.cleanup_temp_file(temp_download_path)
                        if decompressed_temp.exists():
                            self.cleanup_temp_file(decompressed_temp)
                        
                        global_models_progress_store[model_path] = {
                            "progress": 0,
                            "status": "failed",
                            "message": "❌ Decompression failed"
                        }
                        return False
                    
                    # Clean up compressed temp file
                    self.cleanup_temp_file(temp_download_path)
                    final_temp_path = decompressed_temp

                # Move from temp to final location
                try:
                    if self.move_temp_to_final(final_temp_path, local_path, model_path):
                        # Get final file size
                        final_size = 0
                        if local_path.exists():
                            final_size = local_path.stat().st_size
                            
                            size_msg = f"({final_size} bytes)"
                            if is_compressed:
                                size_msg += f" [was compressed: {total_size} bytes]"
                            print(f"✅ Download complete: {model_path} {size_msg}")

                        # Register the model with the configuration manager
                        if MODEL_CONFIG_AVAILABLE:
                            try:
                                model_config_manager.register_s3_model(
                                    local_path=str(local_path),
                                    s3_path=f"s3://{self.bucket}/{actual_s3_key}",
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
                            "total_size": final_size,  # Use actual uncompressed size
                            "downloaded_size": final_size,
                            "message": "✅ Download complete!"
                        }
                        return True
                    else:
                        # Move failed, clean up temp file
                        self.cleanup_temp_file(final_temp_path)
                        return False
                except Exception as e:
                    print(f"Error moving temp file to final location: {e}")
                    self.cleanup_temp_file(final_temp_path)
                    return False
            else:
                print(f"❌ Download failed: {model_path}")
                # Clean up temp file on failure
                if temp_download_path.exists():
                    try:
                        temp_download_path.unlink()
                        print(f"🗑️ Removed failed temp file: {temp_download_path}")
                    except OSError as e:
                        print(f"Error removing failed temp file {temp_download_path}: {e}")

                global_models_progress_store[model_path] = {
                    "progress": 0,
                    "status": "failed",
                    "total_size": total_size,
                    "downloaded_size": 0,
                    "message": "❌ Download failed"
                }
                return False

        except Exception as e:
            print(f"💥 Error downloading model {model_path}: {e}")
            # Clean up temp file on exception
            if 'temp_download_path' in locals() and temp_download_path.exists():
                try:
                    temp_download_path.unlink()
                    print(f"🗑️ Removed temp file after error: {temp_download_path}")
                except OSError as cleanup_error:
                    print(f"Error removing temp file {temp_download_path}: {cleanup_error}")

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

    async def list_s3_objects(self, prefix=""):
        """List S3 objects using centralized S3 client with transparent compression handling"""
        if not self.s3_client or not self.aws_configured:
            return []

        try:
            # Get raw list from S3
            raw_objects = await self.s3_client.list_objects(
                f"pod_sessions/global_shared/models/{prefix}"
            )
            
            # Process objects to handle compression transparently
            processed_objects = []
            compressed_files = {}  # Track compressed versions
            
            # First pass: identify compressed and uncompressed files
            for obj in raw_objects:
                if obj['type'] == 'file':
                    key = obj['key']
                    if key.endswith('.tar.zstd'):
                        # This is a compressed file (.tar.zstd)
                        original_key = key[:-9]  # Remove .tar.zstd
                        compressed_files[original_key] = obj
                    elif key.endswith('.tar.zst'):
                        # This is a compressed file (.tar.zst)
                        original_key = key[:-8]  # Remove .tar.zst
                        compressed_files[original_key] = obj
                    else:
                        # Regular file - add it for now
                        processed_objects.append(obj)
            
            # Second pass: for each regular file, check if compressed version exists
            final_objects = []
            for obj in processed_objects:
                if obj['type'] == 'file':
                    key = obj['key']
                    
                    if key in compressed_files:
                        # Compressed version exists - use it but show uncompressed info
                        compressed_obj = compressed_files[key]
                        
                        # Get metadata from compressed file to find uncompressed size
                        metadata = await self.s3_client.head_object(compressed_obj['key'])
                        
                        # Create transparent object showing uncompressed info
                        transparent_obj = {
                            'key': key,  # Uncompressed key for client
                            'type': 'file',
                            'size': obj['size'],  # Default to compressed size
                            'last_modified': compressed_obj['last_modified'],
                            'etag': compressed_obj['etag'],
                            'metadata': metadata.get('metadata', {}) if metadata else {},
                            '_compressed': True,
                            '_compressed_key': compressed_obj['key'],
                            '_compressed_size': compressed_obj['size']
                        }
                        
                        # Try to get uncompressed size from metadata
                        if metadata and 'metadata' in metadata:
                            meta = metadata['metadata']
                            if 'uncompressed-size' in meta:
                                try:
                                    transparent_obj['size'] = int(meta['uncompressed-size'])
                                except (ValueError, TypeError):
                                    pass
                        
                        final_objects.append(transparent_obj)
                        # Remove from compressed_files so we don't add it again
                        del compressed_files[key]
                    else:
                        # No compressed version - add as-is
                        final_objects.append(obj)
            
            # Third pass: add remaining compressed files (those without uncompressed versions)
            for original_key, compressed_obj in compressed_files.items():
                # Get metadata for uncompressed size
                metadata = await self.s3_client.head_object(compressed_obj['key'])
                
                transparent_obj = {
                    'key': original_key,  # Show uncompressed key
                    'type': 'file',
                    'size': compressed_obj['size'],  # Default to compressed size
                    'last_modified': compressed_obj['last_modified'],
                    'etag': compressed_obj['etag'],
                    'metadata': metadata.get('metadata', {}) if metadata else {},
                    '_compressed': True,
                    '_compressed_key': compressed_obj['key'],
                    '_compressed_size': compressed_obj['size']
                }
                
                # Try to get uncompressed size from metadata
                if metadata and 'metadata' in metadata:
                    meta = metadata['metadata']
                    if 'uncompressed-size' in meta:
                        try:
                            transparent_obj['size'] = int(meta['uncompressed-size'])
                        except (ValueError, TypeError):
                            pass
                
                final_objects.append(transparent_obj)
            
            # Add directory objects as-is
            for obj in raw_objects:
                if obj['type'] == 'directory':
                    final_objects.append(obj)
            
            return final_objects
            
        except Exception as e:
            print(f"Error listing objects with centralized client: {e}")
            return []

    async def cancel_download(self, model_path):
        """Cancel an active download and clean up destination file if needed"""
        if model_path in self.active_downloads:
            print(f"🚫 Cancelling download for {model_path}")
            download_info = self.active_downloads[model_path]
            download_info["cancelled"] = True
            
            # Get local file info for cleanup
            local_path_str = download_info.get("local_path")
            expected_size = download_info.get("expected_size", 0)
            
            # Clean up destination file if it exists and matches expected size
            if local_path_str:
                try:
                    from pathlib import Path
                    local_path = Path(local_path_str)
                    
                    if local_path.exists():
                        current_size = local_path.stat().st_size
                        
                        # Delete if file size equals expected size (complete download)
                        # or if we have a partial download that we want to clean up
                        # Only clean up if reasonable size or partial content
                        should_cleanup = False
                        cleanup_reason = ""
                        
                        if expected_size > 0 and current_size == expected_size:
                            should_cleanup = True
                            cleanup_reason = "completed download"
                        elif current_size > 0:
                            should_cleanup = True
                            cleanup_reason = "partial download"
                        
                        if should_cleanup:
                            local_path.unlink()
                            size_info = f"({current_size} bytes)"
                            if expected_size > 0:
                                size_info += f" of {expected_size} expected"
                            print(f"🗑️ Removed {cleanup_reason} file: "
                                  f"{local_path.name} {size_info}")
                        
                except Exception as e:
                    print(f"Error cleaning up cancelled download file: {e}")
            
            # Update progress store with cancellation message
            if model_path in global_models_progress_store:
                store = global_models_progress_store[model_path]
                store["status"] = "cancelled"
                store["message"] = "🚫 Download cancelled - Click retry"
            
            # Clean up active download tracking after cancellation
            del self.active_downloads[model_path]
            
            return True
        return False

    async def get_global_models_structure(self, force_refresh=False):
        """Get the structure of available global models from S3 with caching"""
        if not self.s3_client or not self.aws_configured:
            print("S3 client not configured or connected.")
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
                    cache_timestamp = cache_data.get('timestamp', 0)
                    if (current_time - cache_timestamp) < self.cache_ttl:
                        structure = cache_data.get('structure', {})
                        self._structure_cache = structure
                        self._cache_timestamp = cache_timestamp
                        return self._structure_cache
            except Exception as e:
                print(f"Error loading cache: {e}")

        try:
            structure = {}

            print("🔍 Using centralized S3 client for listing models")
            objects = await self.list_s3_objects("")

            for obj in objects:
                if obj['type'] == 'file':
                    key = obj['key']
                    relative_path = key.replace(
                        'pod_sessions/global_shared/models/', ''
                    )
                    
                    # Check if this is a compressed file (from transparent handling)
                    is_compressed = obj.get('_compressed', False)
                    compressed_key = obj.get('_compressed_key', key)
                    compressed_size = obj.get('_compressed_size', obj.get('size', 0))
                    
                    # Use the size from list_s3_objects (already uncompressed if available)
                    size = obj.get('size', 0)

                    # Build nested structure
                    path_components = relative_path.split('/')
                    current_level = structure

                    # Navigate/create nested structure (except last component)
                    for component in path_components[:-1]:
                        if component not in current_level:
                            current_level[component] = {}
                        current_level = current_level[component]

                    # Add the file at the final level
                    if len(path_components) >= 1:
                        filename = path_components[-1]
                        if (filename and filename.strip() and
                                not filename.startswith('.')):
                            file_info = {
                                'type': 'file',
                                'size': size,  # Uncompressed size
                                's3_path': compressed_key,  # Actual S3 key (may be compressed)
                                'local_path': str(
                                    self.models_dir / relative_path  # Uncompressed path
                                )
                            }
                            
                            # Add compression info if applicable
                            if is_compressed:
                                file_info['compressed'] = True
                                file_info['compressed_size'] = compressed_size
                            
                            current_level[filename] = file_info

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
            return {}

    async def upload_model(self, local_path):
        """Upload a model to global storage using centralized S3 client"""
        if not self.s3_client or not self.aws_configured:
            print("❌ S3 client not configured")
            return False

        try:
            local_path = Path(local_path)
            if not local_path.exists():
                print(f"❌ Local file not found: {local_path}")
                return False

            # Get relative path within models directory
            relative_path = local_path.relative_to(self.models_dir)
            s3_key = f"pod_sessions/global_shared/models/{relative_path}"

            print(f"📤 Uploading {local_path} to S3...")
            success = await self.s3_client.upload_file(str(local_path), s3_key)

            if success:
                print(f"✅ Successfully uploaded {local_path} to {s3_key}")
                return True
            else:
                print(f"❌ Failed to upload {local_path}")
                return False

        except Exception as e:
            print(f"💥 Error uploading model {local_path}: {e}")
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
        """Sync all global models to local storage using centralized S3 client"""
        if not self.s3_client or not self.aws_configured:
            print("❌ S3 client not configured")
            return False

        try:
            print("🔄 Syncing all global models...")
            
            # Get structure and download all models
            structure = await self.get_global_models_structure(force_refresh=True)
            
            total_downloads = 0
            successful_downloads = 0
            
            def count_files(struct):
                count = 0
                for value in struct.values():
                    if isinstance(value, dict):
                        if value.get('type') == 'file':
                            count += 1
                        else:
                            count += count_files(value)
                return count
            
            total_files = count_files(structure)
            
            async def download_recursive(struct, path_prefix=""):
                nonlocal total_downloads, successful_downloads
                
                for name, value in struct.items():
                    if isinstance(value, dict):
                        if value.get('type') == 'file':
                            model_path = f"{path_prefix}/{name}" if path_prefix else name
                            if not self.check_model_exists_locally(model_path):
                                total_downloads += 1
                                print(f"📥 Downloading {model_path} ({total_downloads}/{total_files})")
                                success = await self.download_model(model_path)
                                if success:
                                    successful_downloads += 1
                        else:
                            new_prefix = f"{path_prefix}/{name}" if path_prefix else name
                            await download_recursive(value, new_prefix)
            
            await download_recursive(structure)
            
            print(f"✅ Sync complete: {successful_downloads}/{total_downloads} models downloaded")
            return successful_downloads == total_downloads

        except Exception as e:
            print(f"💥 Error syncing all models: {e}")
            return False

    def get_s3_connectivity_status(self):
        """Check S3 connectivity for global models using centralized client"""
        if not self.s3_client:
            return {"connected": False, "error": "S3 client not available"}

        if not self.bucket:
            return {"connected": False, "error": "AWS_BUCKET_NAME not set"}

        try:
            return {
                "connected": self.s3_client.is_connected,
                "error": (self.s3_client.connection_error 
                         if not self.s3_client.is_connected else None),
                "bucket": self.bucket,
                "provider": self.s3_client.config.provider,
                "models_path": f"s3://{self.bucket}/pod_sessions/global_shared/models/"
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
        if category_path:
            local_path = self.models_dir / category_path
        else:
            local_path = self.models_dir

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
            # Get cached global structure (don't force refresh)
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

                        # We're in a specific category - show models
                        category_name = category_path.split('/')[0]
                        if category_name in global_structure:
                            category_models = global_structure[category_name]
                            for model_name, model_data in \
                                    category_models.items():
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
                                    item = local_items[model_name]
                                    item["global_exists"] = True
                                    item["downloadable"] = True
                                    item["s3_path"] = model_data["s3_path"]

        except Exception as e:
            print(f"Error adding global models info: {e}")

        return list(local_items.values())

    async def _decompress_file(self, compressed_path, output_path):
        """Decompress a .tar.zstd file to the output path"""
        try:
            if not compressed_path.endswith('.tmp'):
                # If it's not a temp file, it might be the final compressed file
                temp_compressed = Path(compressed_path)
            else:
                temp_compressed = Path(compressed_path)
            
            if not temp_compressed.exists():
                print(f"❌ Compressed file not found: {temp_compressed}")
                return False
            
            # Use zstd and tar for decompression
            # First decompress with zstd, then extract with tar
            print(f"🔄 Decompressing {temp_compressed.name}...")
            
            try:
                # Method 1: Try using zstd command if available (based on working bash logic)
                print(f"🔄 Using zstd command for decompression...")
                
                # Create temporary output directory for extraction
                output_dir = Path(output_path).parent
                
                # Use subprocess to pipe zstd output directly to tar (like the bash version)
                zstd_cmd = ['zstd', '-d', '-c', str(temp_compressed)]
                tar_cmd = ['tar', '-xf', '-', '-C', str(output_dir)]
                
                # Run zstd decompression piped to tar extraction
                zstd_process = subprocess.Popen(zstd_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                tar_process = subprocess.Popen(tar_cmd, stdin=zstd_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Close zstd stdout in parent process to avoid broken pipe
                zstd_process.stdout.close()
                
                # Wait for both processes to complete
                tar_output, tar_error = tar_process.communicate()
                zstd_process.wait()
                
                if zstd_process.returncode != 0:
                    zstd_stderr = zstd_process.stderr.read().decode() if zstd_process.stderr else "Unknown error"
                    print(f"❌ zstd decompression failed: {zstd_stderr}")
                    return False
                
                if tar_process.returncode != 0:
                    tar_stderr = tar_error.decode() if tar_error else "Unknown error"
                    print(f"❌ tar extraction failed: {tar_stderr}")
                    return False
                
                # Find the extracted file in the output directory (should be only one)
                extracted_files = [f for f in output_dir.iterdir() if f.is_file() and f.name != temp_compressed.name]
                
                if not extracted_files:
                    print(f"❌ No files found after extraction in {output_dir}")
                    return False
                
                if len(extracted_files) > 1:
                    print(f"⚠️ Multiple files found after extraction, using first one: {[f.name for f in extracted_files]}")
                
                extracted_file = extracted_files[0]
                
                # Move the extracted file to the expected output path
                if extracted_file != Path(output_path):
                    extracted_file.rename(output_path)
                    print(f"✅ Moved extracted file to: {output_path}")
                else:
                    print(f"✅ File extracted to correct location: {output_path}")
                
                return True
                
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
                print(f"❌ Command-line decompression failed: {e}")
                # Method 2: Fallback to Python libraries
                try:
                    import zstandard as zstd
                    
                    with open(temp_compressed, 'rb') as compressed_file:
                        dctx = zstd.ZstdDecompressor()
                        with dctx.stream_reader(compressed_file) as reader:
                            with tarfile.open(fileobj=reader, mode='r|') as tar:
                                members = tar.getmembers()
                                if len(members) != 1:
                                    print(f"❌ Expected 1 file in archive, found {len(members)}")
                                    return False
                                
                                member = members[0]
                                with tar.extractfile(member) as source:
                                    with open(output_path, 'wb') as dest:
                                        dest.write(source.read())
                    
                    print(f"✅ Decompressed to {output_path}")
                    return True
                    
                except ImportError:
                    print("❌ zstandard library not available for decompression")
                    return False
        
        except Exception as e:
            print(f"❌ Decompression failed: {e}")
            return False

    def clear_cache(self):
        """Clear all caches to ensure fresh data retrieval"""
        self._structure_cache = None
        self._cache_timestamp = 0
        
        # Also clear disk cache if it exists
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                print("🗑️ Cleared disk cache for global models structure")
            except Exception as e:
                print(f"⚠️ Failed to clear disk cache: {e}")
        
        print("✅ Global models cache cleared")

