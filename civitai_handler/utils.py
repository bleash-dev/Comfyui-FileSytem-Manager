import os
import re
import tempfile
from pathlib import Path
import folder_paths

class CivitAIUtils:
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

    def parse_civitai_url(self, civitai_url: str) -> dict:
        """
        Parses a CivitAI URL to extract model_id and version_id.
        Returns: {'model_id': str, 'version_id': str or None, 'is_model_url': bool, 'is_direct_download': bool}
        """
        # Pattern 1: Direct API download URLs (e.g., https://civitai.com/api/download/models/1838857?type=Model&format=SafeTensor)
        api_download_match = re.match(r"^(?:https?://(?:www\.)?civitai\.com/)?api/download/models/(?P<version_id>\d+)", civitai_url)
        if api_download_match:
            # Clean URL by removing any existing token parameter
            clean_url = re.sub(r'[&?]token=[^&]*', '', civitai_url)
            
            return {
                "model_id": None,  # We don't have model_id from direct download URLs
                "version_id": api_download_match.group("version_id"),
                "is_model_url": False,
                "is_direct_download": True,
                "download_url": clean_url if clean_url.startswith('http') else f"https://civitai.com/{clean_url.lstrip('/')}"
            }
        
        # Pattern 2: Model page URLs (e.g., https://civitai.com/models/123456)
        model_match = re.match(r"^(?:https?://(?:www\.)?civitai\.com/)?models/(?P<model_id>\d+)(?:\?.*)?$", civitai_url)
        if model_match:
            return {
                "model_id": model_match.group("model_id"),
                "version_id": None,
                "is_model_url": True,
                "is_direct_download": False
            }
        
        # Pattern 3: Model with version (e.g., https://civitai.com/models/123456?modelVersionId=789)
        version_match = re.match(r"^(?:https?://(?:www\.)?civitai\.com/)?models/(?P<model_id>\d+).*[?&]modelVersionId=(?P<version_id>\d+)", civitai_url)
        if version_match:
            return {
                "model_id": version_match.group("model_id"),
                "version_id": version_match.group("version_id"),
                "is_model_url": True,
                "is_direct_download": False
            }
        
        # Pattern 4: Direct model ID (just numbers)
        if re.match(r"^\d+$", civitai_url):
            return {
                "model_id": civitai_url,
                "version_id": None,
                "is_model_url": True,
                "is_direct_download": False
            }
        
        # Pattern 5: Model ID with version (123456:789)
        id_version_match = re.match(r"^(?P<model_id>\d+):(?P<version_id>\d+)$", civitai_url)
        if id_version_match:
            return {
                "model_id": id_version_match.group("model_id"),
                "version_id": id_version_match.group("version_id"),
                "is_model_url": True,
                "is_direct_download": False
            }
            
        raise ValueError(f"Invalid CivitAI URL or model ID: {civitai_url}")

    def determine_model_type_from_metadata(self, model_info: dict) -> str:
        """Determine ComfyUI model type from CivitAI model metadata"""
        model_type = model_info.get('type', '').lower()
        
        type_mapping = {
            'checkpoint': 'checkpoints',
            'lora': 'loras',
            'lycoris': 'loras',
            'controlnet': 'controlnet',
            'vae': 'vae',
            'embedding': 'embeddings',
            'textualinversion': 'embeddings',
            'upscaler': 'upscale_models',
            'poses': 'poses',
            'wildcards': 'wildcards'
        }
        
        return type_mapping.get(model_type, 'checkpoints')

    def get_safe_filename(self, filename: str) -> str:
        """Generate a safe filename by removing invalid characters"""
        # Remove invalid characters
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        safe_name = safe_name.strip()
        
        if not safe_name:
            safe_name = "civitai_model"
        
        return safe_name

    def create_temp_file(self, filename: str) -> str:
        """Create a temporary file path"""
        temp_dir = Path(tempfile.gettempdir())
        safe_filename = self.get_safe_filename(filename)
        temp_path = temp_dir / f"civitai_temp_{abs(hash(safe_filename)) % 10000}_{safe_filename}"
        return str(temp_path)

    def cleanup_temp_file(self, temp_path: str):
        """Clean up temporary file"""
        try:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()
                print(f"🗑️ Cleaned up temp file: {temp_path}")
        except Exception as e:
            print(f"⚠️ Failed to clean up temp file {temp_path}: {e}")
