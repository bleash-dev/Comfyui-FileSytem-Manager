import os
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import folder_paths

class GlobalModelsManager:
    def __init__(self):
        self.comfyui_base = folder_paths.base_path
        self.models_dir = Path(self.comfyui_base) / "models"
        self.aws_bucket_name = os.environ.get("AWS_BUCKET_NAME")
        self.s3_global_models_path = f"s3:{self.aws_bucket_name}/pod_sessions/global_shared/models/"
        self.cache_file = self.models_dir / ".global_models_cache.json"
        self.cache_duration = timedelta(hours=1)
        
    async def get_global_models_structure(self, force_refresh=False):
        """Get the structure of global models from S3, using cache if available"""
        if not force_refresh and self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    cache_time = datetime.fromisoformat(cache_data['timestamp'])
                    if datetime.now() - cache_time < self.cache_duration:
                        return cache_data['structure']
            except (json.JSONDecodeError, KeyError, ValueError):
                pass
        
        # Fetch fresh data from S3
        structure = await self._fetch_s3_structure()
        
        # Cache the result
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'structure': structure
        }
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        return structure
    
    async def _fetch_s3_structure(self):
        """Fetch models structure - only go one level deep per category"""
        try:
            # Get all items in models directory with depth limit
            process = await asyncio.create_subprocess_exec(
                'rclone', 'lsjson', self.s3_global_models_path, '--max-depth', '2',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"Error fetching S3 structure: {stderr.decode()}")
                return {}
            
            s3_items = json.loads(stdout.decode())
            structure = {}
            
            for item in s3_items:
                path = item['Path']
                path_parts = path.split('/')
                
                if len(path_parts) < 1:
                    continue
                
                category = path_parts[0]  # e.g., "checkpoints", "loras", etc.
                
                # Initialize category if not exists
                if category not in structure:
                    structure[category] = {}
                
                # Only handle direct files/folders in categories (max 2 levels: category/item)
                if len(path_parts) == 1:
                    # This is the category directory itself
                    continue
                elif len(path_parts) == 2:
                    # This is a direct file/folder in the category
                    item_name = path_parts[1]
                    structure[category][item_name] = {
                        'type': 'file' if not item.get('IsDir', False) else 'directory',
                        'size': item.get('Size', 0),
                        'modified': item.get('ModTime', ''),
                        's3_path': path,
                        'local_path': str(self.models_dir / path),
                        'local_exists': (self.models_dir / path).exists(),
                        'downloadable': True
                    }
            
            return structure
        
        except Exception as e:
            print(f"Error fetching S3 models structure: {e}")
            return {}
    
    async def download_model(self, s3_relative_path, progress_callback=None):
        """Download a model from S3 with progress tracking"""
        local_path = self.models_dir / s3_relative_path
        s3_full_path = f"{self.s3_global_models_path}{s3_relative_path}"
        
        # Ensure local directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Use rclone copy with progress
            if local_path.suffix:  # It's a file
                process = await asyncio.create_subprocess_exec(
                    'rclone', 'copyto', s3_full_path, str(local_path), '--progress',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            else:  # It's a directory
                process = await asyncio.create_subprocess_exec(
                    'rclone', 'sync', s3_full_path, str(local_path), '--progress',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            
            # Monitor progress
            if progress_callback:
                asyncio.create_task(self._monitor_download_progress(local_path, progress_callback))
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Update cache to reflect the new download
                await self.get_global_models_structure(force_refresh=True)
                return True
            else:
                print(f"Download failed: {stderr.decode()}")
                return False
        
        except Exception as e:
            print(f"Error downloading model: {e}")
            return False
    
    async def _monitor_download_progress(self, local_path, progress_callback):
        """Monitor download progress by checking file size"""
        start_time = asyncio.get_event_loop().time()
        
        while not local_path.exists():
            await asyncio.sleep(0.5)
        
        while True:
            try:
                current_size = local_path.stat().st_size
                # Call progress callback with current size
                progress_callback(current_size)
                await asyncio.sleep(1)
                
                # Check if download is complete (file size hasn't changed for 2 seconds)
                await asyncio.sleep(2)
                new_size = local_path.stat().st_size
                if new_size == current_size:
                    break
                    
            except FileNotFoundError:
                break
            except Exception as e:
                print(f"Error monitoring download progress: {e}")
                break
    
    async def sync_new_model_to_global(self, local_relative_path):
        """Sync a newly downloaded model to global shared storage"""
        local_path = self.models_dir / local_relative_path
        s3_destination = f"{self.s3_global_models_path}{local_relative_path}"
        
        if not local_path.exists():
            return False
        
        try:
            process = await asyncio.create_subprocess_exec(
                'rclone', 'copy', str(local_path), 
                f"{self.s3_global_models_path}{local_relative_path.replace(local_path.name, '')}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print(f"Successfully synced new model to global: {local_relative_path}")
                # Update cache
                await self.get_global_models_structure(force_refresh=True)
                return True
            else:
                print(f"Failed to sync model to global: {stderr.decode()}")
                return False
        
        except Exception as e:
            print(f"Error syncing model to global: {e}")
            return False
    
    def get_local_models_structure(self):
        """Get the structure of local models"""
        structure = {}
        
        if not self.models_dir.exists():
            return structure
        
        for category_dir in self.models_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                structure[category_dir.name] = self._get_directory_structure(category_dir)
        
        return structure
    
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

