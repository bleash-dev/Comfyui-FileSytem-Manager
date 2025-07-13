#!/usr/bin/env python3
"""
Model Configuration Integration for ComfyUI File System Manager
Integrates with the model_config_manager.sh script to track downloaded models
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional

# Set up logging
logger = logging.getLogger(__name__)


class ModelConfigManager:
    """Integration class for the model configuration manager shell script"""
    
    def __init__(self):
        self.network_volume = os.environ.get('NETWORK_VOLUME', '/workspace')
        self.script_path = (f"{self.network_volume}/scripts/"
                            f"model_config_manager.sh")
        self.comfyui_base = None
        
        # Try to get ComfyUI base path
        try:
            import folder_paths
            self.comfyui_base = folder_paths.base_path
        except ImportError:
            # Fallback if folder_paths not available
            self.comfyui_base = os.environ.get('COMFYUI_BASE',
                                               '/workspace/ComfyUI')
        
        logger.info(f"ModelConfigManager initialized with script: "
                    f"{self.script_path}")
    
    def _determine_model_group(self, local_path: str,
                               model_type: str = None) -> str:
        """Determine the model group based on the local path and type"""
        local_path = local_path.lower()
        
        # First, try to use provided model_type
        if model_type:
            type_mapping = {
                'checkpoint': 'checkpoints',
                'checkpoints': 'checkpoints',
                'vae': 'vae',
                'lora': 'loras',
                'loras': 'loras',
                'controlnet': 'controlnet',
                'embedding': 'embeddings',
                'embeddings': 'embeddings',
                'upscale': 'upscale_models',
                'upscale_models': 'upscale_models'
            }
            mapped_type = type_mapping.get(model_type.lower())
            if mapped_type:
                return mapped_type
        
        # Fallback to path-based detection
        if 'checkpoints' in local_path:
            return 'checkpoints'
        elif 'vae' in local_path:
            return 'vae'
        elif 'loras' in local_path or 'lora' in local_path:
            return 'loras'
        elif 'controlnet' in local_path:
            return 'controlnet'
        elif 'embeddings' in local_path:
            return 'embeddings'
        elif 'upscale' in local_path:
            return 'upscale_models'
        elif 'ipadapter' in local_path:
            return 'ipadapter'
        elif 'clip' in local_path:
            return 'clip'
        elif 'unet' in local_path:
            return 'unet'
        else:
            return 'other'
    
    def _determine_model_type_from_path(self, local_path: str) -> str:
        """Extract model type from ComfyUI models directory structure.
        
        Looks for '/models/MODEL_TYPE/' pattern in the path and returns
        MODEL_TYPE. For example:
        '/ComfyUI/models/checkpoints/model.safetensors' -> 'checkpoints'
        """
        try:
            # Normalize path separators
            normalized_path = str(local_path).replace('\\', '/')
            
            # Look for '/models/' pattern
            models_index = normalized_path.find('/models/')
            if models_index == -1:
                return "unknown"
            
            # Extract everything after '/models/'
            # 8 = len('/models/')
            after_models = normalized_path[models_index + 8:]
            
            # Find the first directory after /models/
            parts = after_models.split('/')
            if parts and parts[0]:
                return parts[0]
            else:
                return ""
                
        except Exception as e:
            logger.warning(f"Could not extract model type from path "
                           f"{local_path}: {e}")
            return "unknown"
    
    def _get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size safely"""
        try:
            if os.path.exists(file_path):
                return os.path.getsize(file_path)
        except Exception as e:
            logger.warning(f"Could not get file size for {file_path}: {e}")
        return None
    
    def _run_script_command(self, command: str) -> tuple[bool, str]:
        """Run a command using the model config manager script"""
        try:
            # Source the script and run the command
            full_command = f"source {self.script_path} && {command}"
            result = subprocess.run(
                ['bash', '-c', full_command],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.debug(f"Script command succeeded: {command}")
                return True, result.stdout
            else:
                logger.error(f"Script command failed: {command}, "
                             f"stderr: {result.stderr}")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            logger.error(f"Script command timed out: {command}")
            return False, "Command timed out"
        except Exception as e:
            logger.error(f"Error running script command: {command}, "
                         f"error: {e}")
            return False, str(e)
    
    def register_s3_model(self, local_path: str, s3_path: str,
                          model_name: str = None,
                          model_type: str = None,
                          download_link: str = None,
                          sym_linked_from: str = None) -> bool:
        """Register a model downloaded from S3"""
        try:
            group = self._determine_model_group(local_path, model_type)
            file_size = self._get_file_size(local_path)
            
            # Extract model name from path if not provided
            if not model_name:
                model_name = self._extract_model_name_from_path(local_path)
            
            # Create model object for S3 downloads
            model_object = {
                "originalS3Path": s3_path,
                "localPath": local_path,
                "modelName": model_name,
                "directoryGroup": group,
                "downloadUrl": s3_path,
                "downloadSource": "s3"
            }
            
            # Add optional fields
            if file_size:
                model_object["modelSize"] = file_size
            if download_link:
                model_object["downloadUrl"] = download_link
            if sym_linked_from:
                model_object["symLinkedFrom"] = sym_linked_from
            
            # Convert to JSON string
            model_json = json.dumps(model_object)
            
            # Create the command
            command = f"create_or_update_model '{group}' '{model_json}'"
            
            success, output = self._run_script_command(command)
            
            if success:
                logger.info(f"Successfully registered S3 model: "
                            f"{local_path} -> {s3_path}")
                return True
            else:
                logger.error(f"Failed to register S3 model: {output}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering S3 model: {e}")
            return False
    
    def register_internet_model(self, local_path: str, download_url: str,
                                model_name: str = None,
                                model_type: str = None,
                                source: str = "internet") -> bool:
        """Register a model downloaded from the internet
        (HuggingFace, CivitAI, etc.)"""
        try:
            group = self._determine_model_group(local_path, model_type)
            file_size = self._get_file_size(local_path)
            
            # Extract model name from path if not provided
            if not model_name:
                model_name = self._extract_model_name_from_path(local_path)
            
            # Create model object for internet downloads
            model_object = {
                "localPath": local_path,
                "modelName": model_name,
                "directoryGroup": group,
                "downloadUrl": download_url,
                "downloadSource": source
            }
            
            # Add optional fields
            if file_size:
                model_object["modelSize"] = file_size
            
            # Convert to JSON string
            model_json = json.dumps(model_object)
            
            # Create the command
            command = f"create_or_update_model '{group}' '{model_json}'"
            
            success, output = self._run_script_command(command)
            
            if success:
                logger.info(f"Successfully registered internet model: "
                            f"{local_path} from {source}")
                return True
            else:
                logger.error(f"Failed to register internet model: {output}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering internet model: {e}")
            return False
    
    def register_huggingface_model(self, local_path: str, repo_id: str,
                                   filename: str,
                                   model_type: str = None) -> bool:
        """Register a model downloaded from HuggingFace"""
        download_url = f"https://huggingface.co/{repo_id}"
        if filename:
            download_url += f"/blob/main/{filename}"
        
        model_name = filename or self._extract_model_name_from_path(local_path)
        return self.register_internet_model(
            local_path=local_path,
            download_url=download_url,
            model_name=model_name,
            model_type=model_type,
            source="huggingface"
        )
    
    def register_civitai_model(self, local_path: str, model_id: str = None,
                               version_id: str = None,
                               direct_url: str = None,
                               model_type: str = None) -> bool:
        """Register a model downloaded from CivitAI"""
        if direct_url:
            download_url = direct_url
        elif model_id:
            download_url = f"https://civitai.com/models/{model_id}"
            if version_id:
                download_url += f"?modelVersionId={version_id}"
        else:
            download_url = "https://civitai.com"
        
        model_name = self._extract_model_name_from_path(local_path)
        return self.register_internet_model(
            local_path=local_path,
            download_url=download_url,
            model_name=model_name,
            model_type=model_type,
            source="civitai"
        )
    
    def register_google_drive_model(self, local_path: str, drive_url: str,
                                    model_type: str = None) -> bool:
        """Register a model downloaded from Google Drive"""
        model_name = self._extract_model_name_from_path(local_path)
        return self.register_internet_model(
            local_path=local_path,
            download_url=drive_url,
            model_name=model_name,
            model_type=model_type,
            source="google_drive"
        )
    
    def register_direct_url_model(self, local_path: str, url: str,
                                  model_type: str = None) -> bool:
        """Register a model downloaded from a direct URL"""
        model_name = self._extract_model_name_from_path(local_path)
        return self.register_internet_model(
            local_path=local_path,
            download_url=url,
            model_name=model_name,
            model_type=model_type,
            source="direct_url"
        )
    
    def register_huggingface_repo(self, repo_path: str, repo_id: str,
                                  model_type: str = None,
                                  source_url: str = None) -> int:
        """Register all files in a HuggingFace repository download.
        Files are registered in their original repository structure."""
        try:
            repo_path = Path(repo_path)
            if not repo_path.exists():
                logger.error(f"Repository path does not exist: {repo_path}")
                return 0
            
            # Get all model files in the repository
            model_files = []
            for file_path in repo_path.rglob("*"):
                if file_path.is_file():
                    # Check if it's a model file based on extension
                    ext = file_path.suffix.lower()
                    if ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin',
                               '.json', '.yml', '.yaml', '.py', '.txt', '.md']:
                        # Calculate relative path within the repo
                        rel_path = file_path.relative_to(repo_path)
                        model_files.append((file_path, rel_path))
            
            logger.info(f"Found {len(model_files)} files in repo "
                        f"{repo_id}")
            
            # Register each file in its original location
            success_count = 0
            for file_path, rel_path in model_files:
                try:
                    # Use the actual download path structure as the group
                    # This preserves the original repository organization
                    download_url = f"https://huggingface.co/{repo_id}"
                    if source_url:
                        download_url = source_url
                    
                    # Create model object preserving original structure
                    file_size = self._get_file_size(str(file_path))
                    
                    # Use backend convention for model name extraction
                    model_name = self._extract_model_name_from_path(
                        str(file_path))
                    
                    model_object = {
                        "localPath": str(file_path),
                        "modelName": model_name,
                        "repositoryPath": str(rel_path),
                        "repositoryId": repo_id,
                        "downloadUrl": download_url,
                        "downloadSource": "huggingface_repo"
                    }
                    
                    # Add optional fields
                    if file_size:
                        model_object["modelSize"] = file_size
                    if model_type:
                        model_object["modelType"] = model_type
                    
                    # Use the repository name as the group to keep files
                    # together
                    repo_name = repo_id.split('/')[-1]
                    
                    # Determine the group based on where the repo was
                    # downloaded - extract ComfyUI models directory structure
                    group = self._determine_model_type_from_path(
                        str(file_path))
                    if group == "unknown" or group == "":
                        # Fallback to using the repository structure
                        group = f"repositories/{repo_name}"
                    
                    # Convert to JSON string
                    model_json = json.dumps(model_object)
                    
                    # Create the command
                    command = (f"create_or_update_model '{group}' "
                               f"'{model_json}'")
                    
                    success, output = self._run_script_command(command)
                    
                    if success:
                        success_count += 1
                        logger.debug(f"Registered: {rel_path}")
                    else:
                        logger.warning(f"Failed to register {rel_path}: "
                                       f"{output}")
                        
                except Exception as e:
                    logger.error(f"Error registering file {rel_path}: {e}")
            
            logger.info(f"Successfully registered {success_count}/"
                        f"{len(model_files)} files from repo {repo_id}")
            return success_count
            
        except Exception as e:
            logger.error(f"Error registering HuggingFace repo {repo_id}: {e}")
            return 0
    
    def _extract_model_name_from_path(self, file_path: str) -> str:
        """Extract model name using the same convention as backend.
        
        This matches the extractModelName function from the backend:
        - Looks for 'models/' pattern (equivalent to backend's modelsPrefix)
        - Removes the models prefix
        - Skips the first part (group) and returns everything after
        - Handles nested directories like: {group}/{subdir}/{modelName}
        """
        try:
            # Normalize path separators
            normalized_path = str(file_path).replace('\\', '/')
            
            # Look for '/models/' pattern (equivalent to backend's prefix)
            models_prefix = '/models/'
            models_index = normalized_path.find(models_prefix)
            
            if models_index == -1:
                # Fallback to basename for non-standard paths
                return Path(file_path).name
            
            # Remove everything up to and including '/models/'
            relative_path = normalized_path[models_index + len(models_prefix):]
            path_parts = relative_path.split('/')
            
            if len(path_parts) < 2:
                # If no group or model name, return the whole relative path
                return relative_path
            
            # Skip the first part (group) and return everything after
            # Handles nested dirs like: {group}/{subdir}/{modelName}
            return '/'.join(path_parts[1:])
            
        except Exception as e:
            logger.warning(f"Could not extract model name from path "
                           f"{file_path}: {e}")
            return Path(file_path).name


# Global instance
model_config_manager = ModelConfigManager()
