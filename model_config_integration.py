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
                full_command,
                shell=True,
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
                          download_link: str = None) -> bool:
        """Register a model downloaded from S3"""
        try:
            group = self._determine_model_group(local_path, model_type)
            file_size = self._get_file_size(local_path)
            
            # Extract model name from path if not provided
            if not model_name:
                model_name = Path(local_path).stem
            
            # Create model object for S3 downloads
            model_object = {
                "originalS3Path": s3_path,
                "localPath": local_path,
                "modelName": model_name,
                "directoryGroup": group,
                "downloadSource": "s3"
            }
            
            # Add optional fields
            if file_size:
                model_object["modelSize"] = file_size
            if download_link:
                model_object["downloadLink"] = download_link
            
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
                model_name = Path(local_path).stem
            
            # Create model object for internet downloads
            model_object = {
                "localPath": local_path,
                "modelName": model_name,
                "directoryGroup": group,
                "downloadLink": download_url,
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
                                   filename: str = None,
                                   model_type: str = None) -> bool:
        """Register a model downloaded from HuggingFace"""
        download_url = f"https://huggingface.co/{repo_id}"
        if filename:
            download_url += f"/blob/main/{filename}"
        
        model_name = filename or Path(local_path).name
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
        
        model_name = Path(local_path).stem
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
        model_name = Path(local_path).stem
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
        model_name = Path(local_path).stem
        return self.register_internet_model(
            local_path=local_path,
            download_url=url,
            model_name=model_name,
            model_type=model_type,
            source="direct_url"
        )


# Global instance
model_config_manager = ModelConfigManager()
