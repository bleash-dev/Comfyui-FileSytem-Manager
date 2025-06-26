import os
import re
import shutil
import tempfile
from pathlib import Path
import folder_paths

class HuggingFaceUtils:
    def __init__(self):
        self.comfyui_base = folder_paths.base_path
        self.hf_host = "https://huggingface.co"

    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable units"""
        if size_bytes == 0:
            return "0 B"
        
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
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

    def parse_hf_url(self, hf_url: str) -> dict:
        """
        Parses a Hugging Face URL to extract repo_id and optionally filename/subfolder.
        Returns: {'repo_id': str, 'filename': str or None, 'is_file_url': bool}
        """
        # Pattern 1: File URLs (blob/resolve with filename)
        file_match = re.match(r"^(?:https?://huggingface\.co/)?(?P<repo_id>[^/]+/[^/]+)/(?:blob|resolve)/[^/]+/(?P<filename>.+)$", hf_url)
        if file_match:
            data = file_match.groupdict()
            return {
                "repo_id": data["repo_id"],
                "filename": data["filename"],
                "is_file_url": True,
                "hf_url": hf_url
            }
        
        # Pattern 2: Repository URLs (with or without /tree/main or other suffixes)
        repo_match = re.match(r"^(?:https?://huggingface\.co/)?(?P<repo_id>[^/]+/[^/]+)(?:/(?:tree|commits?|discussions?|settings?)(?:/.*)?)?/?$", hf_url)
        if repo_match:
            data = repo_match.groupdict()
            return {
                "repo_id": data["repo_id"],
                "filename": None,
                "is_file_url": False,
                "hf_url": self.hf_host in hf_url and hf_url or f"{self.hf_host}/{hf_url}"
            }
        
        # Pattern 3: Just a repo_id like "username/repo_name"
        if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", hf_url):
            return {
                "repo_id": hf_url, 
                "filename": None, 
                "is_file_url": False, 
                "hf_url": f"{self.hf_host}/{hf_url}"
            }

        raise ValueError(f"Invalid Hugging Face URL or repo_id: {hf_url}")

    def convert_size_to_bytes(self, value: float, unit: str) -> int:
        """Convert size value with unit to bytes"""
        multipliers = {
            'B': 1,
            '': 1,  # Default to bytes
            'K': 1024,
            'M': 1024 ** 2,
            'G': 1024 ** 3,
            'T': 1024 ** 4
        }
        
        multiplier = multipliers.get(unit.upper(), 1)
        return int(value * multiplier)

    def cleanup_cache_file(self, cache_path, *additional_paths):
        """Clean up a single cache file and any additional related paths"""
        paths_to_clean = [cache_path] + list(additional_paths)
        
        for path in paths_to_clean:
            if path and Path(path).exists():
                try:
                    if Path(path).is_file():
                        os.unlink(path)
                        print(f"🗑️ Cleaned up cache file: {path}")
                    elif Path(path).is_dir():
                        shutil.rmtree(path)
                        print(f"🗑️ Cleaned up cache directory: {path}")
                except Exception as e:
                    print(f"⚠️ Failed to clean up cache path {path}: {e}")

    def cleanup_cache_files(self, cache_paths):
        """Clean up multiple cache files and directories"""
        if not cache_paths:
            return
        
        print(f"🗑️ Cleaning up {len(cache_paths)} cache entries...")
        
        # Group cache paths by their parent directories to optimize cleanup
        cache_dirs = set()
        for cache_path in cache_paths:
            if cache_path and Path(cache_path).exists():
                try:
                    path_obj = Path(cache_path)
                    
                    if path_obj.is_file():
                        os.unlink(cache_path)
                        print(f"🗑️ Cleaned up cache file: {cache_path}")
                        cache_dirs.add(path_obj.parent)
                    elif path_obj.is_dir():
                        shutil.rmtree(cache_path)
                        print(f"🗑️ Cleaned up cache directory: {cache_path}")
                        
                except Exception as e:
                    print(f"⚠️ Failed to clean up cache path {cache_path}: {e}")
        
        # Clean up empty cache directories
        for cache_dir in cache_dirs:
            try:
                if cache_dir.exists() and cache_dir.is_dir():
                    remaining_files = [f for f in cache_dir.iterdir() if not f.name.startswith('.')]
                    if not remaining_files:
                        shutil.rmtree(cache_dir)
                        print(f"🗑️ Cleaned up empty cache directory: {cache_dir}")
            except Exception as e:
                print(f"⚠️ Failed to clean up cache directory {cache_dir}: {e}")

    def resolve_all_symlinks_in_directory(self, directory_path: Path):
        """Recursively resolve all symbolic links in a directory to actual files"""
        cache_paths_to_cleanup = []
        
        try:
            for item in directory_path.rglob('*'):
                if item.is_symlink():
                    try:
                        actual_target = item.resolve()
                        
                        if actual_target.exists():
                            print(f"🔗 Resolving symlink: {item} -> {actual_target}")
                            cache_paths_to_cleanup.append(actual_target)
                            item.unlink()
                            
                            if actual_target.is_file():
                                shutil.copy2(actual_target, item)
                            elif actual_target.is_dir():
                                shutil.copytree(actual_target, item)
                            
                            print(f"✅ Replaced symlink with actual content: {item}")
                        else:
                            print(f"⚠️ Broken symlink found and removed: {item} -> {actual_target}")
                            item.unlink()
                            
                    except Exception as resolve_error:
                        print(f"❌ Error resolving symlink {item}: {resolve_error}")
                        try:
                            item.unlink()
                        except:
                            pass
        except Exception as e:
            print(f"Error resolving symlinks in directory {directory_path}: {e}")
        
        return cache_paths_to_cleanup
