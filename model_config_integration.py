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
        """
        Determine the model group based on the local path and type.
        Maps to ComfyUI's folder_paths structure and node types.
        
        This method supports all core ComfyUI model types and common
        custom node model types, providing granular categorization
        based on:
        
        1. Explicit model_type parameter (if provided)
        2. Path-based detection using ComfyUI's standard folder structure
        3. Common custom node model directory patterns
        
        Core ComfyUI Model Types (from folder_paths.py):
        - checkpoints: Main diffusion models (.ckpt, .safetensors)
        - diffusion_models/unet: UNET models for diffusion
        - vae: Variational AutoEncoders
        - vae_approx: Tiny AutoEncoder models (TAESD)
        - text_encoders/clip: Text encoding models (CLIP, T5, etc.)
        - clip_vision: Vision encoders for image conditioning
        - loras: Low-Rank Adaptation models
        - controlnet: ControlNet and T2I-Adapter models
        - embeddings: Textual inversion embeddings
        - upscale_models: Real-ESRGAN and similar upscaling models
        - style_models: Style transfer models
        - gligen: GLIGEN grounding models
        - hypernetworks: Hypernetwork models
        - photomaker: PhotoMaker models
        - classifiers: Classification models
        - diffusers: HuggingFace Diffusers format models
        
        Common Custom Node Model Types:
        - ipadapter: IP-Adapter models for image prompting
        - animatediff: AnimateDiff motion modules
        - insightface: InsightFace models for face analysis
        - instantid: InstantID models
        - inpaint: Inpainting-specific models
        - segmentation: Segmentation models
        - depth_estimation: Depth estimation models
        - pose_estimation: Pose estimation models (OpenPose, etc.)
        - video_models: Video generation/processing models
        - audio_models: Audio processing models
        
        Args:
            local_path: The local file path to analyze
            model_type: Optional explicit model type override
            
        Returns:
            str: The determined model group/category
        """
        local_path = local_path.lower()
        
        # First, try to use provided model_type
        if model_type:
            type_mapping = {
                # Core model types from ComfyUI nodes.py
                'checkpoint': 'checkpoints',
                'checkpoints': 'checkpoints',
                'diffusion_model': 'diffusion_models',
                'rembg': 'rembg',
                'diffusion_models': 'diffusion_models',
                'unet': 'unet',
                'vae': 'vae',
                'vae_approx': 'vae_approx',
                'text_encoder': 'text_encoders',
                'text_encoders': 'text_encoders',
                'clip': 'clip',
                'clip_vision': 'clip_vision',
                'lora': 'loras',
                'loras': 'loras',
                'controlnet': 'controlnet',
                't2i_adapter': 'controlnet',
                'embedding': 'embeddings',
                'embeddings': 'embeddings',
                'upscale_model': 'upscale_models',
                'upscale_models': 'upscale_models',
                'style_model': 'style_models',
                'style_models': 'style_models',
                'gligen': 'gligen',
                'hypernetwork': 'hypernetworks',
                'hypernetworks': 'hypernetworks',
                'photomaker': 'photomaker',
                'classifier': 'classifiers',
                'classifiers': 'classifiers',
                'diffuser': 'diffusers',
                'diffusers': 'diffusers',
                # Additional custom node types
                'ipadapter': 'ipadapter',
                'ip_adapter': 'ipadapter',
                'animatediff': 'animatediff',
                'motion_module': 'animatediff',
                'insightface': 'insightface',
                'face_analysis': 'insightface',
                'instantid': 'instantid',
                'inpaint': 'inpaint',
                'segmentation': 'segmentation',
                'depth_estimation': 'depth_estimation',
                'pose_estimation': 'pose_estimation',
                'video_model': 'video_models',
                'audio_model': 'audio_models',
            }
            mapped_type = type_mapping.get(model_type.lower())
            if mapped_type:
                return mapped_type
        
        # Comprehensive path-based detection based on ComfyUI's folder
        # structure. Order matters - more specific patterns first
        
        # Core ComfyUI model directories from folder_paths.py
        if any(x in local_path for x in ['checkpoints', 'checkpoint']):
            return 'checkpoints'
        elif any(x in local_path for x in ['diffusion_models', 'unet']):
            return 'diffusion_models'
        elif 'vae_approx' in local_path or 'taesd' in local_path:
            return 'vae_approx'
        elif 'vae' in local_path:
            return 'vae'
        elif 'clip_vision' in local_path:
            return 'clip_vision'
        elif any(x in local_path for x in ['text_encoders', 't5']):
            return 'text_encoders'
        elif any(x in local_path for x in ['loras', 'lora']):
            return 'loras'
        elif any(x in local_path for x in ['controlnet', 't2i_adapter']):
            return 'controlnet'
        elif any(x in local_path for x in ['embeddings', 'embedding']):
            return 'embeddings'
        elif any(x in local_path for x in ['upscale_models', 'upscale']):
            return 'upscale_models'
        elif any(x in local_path for x in ['style_models', 'style']):
            return 'style_models'
        elif 'gligen' in local_path:
            return 'gligen'
        elif any(x in local_path for x in ['hypernetworks', 'hypernetwork']):
            return 'hypernetworks'
        elif 'photomaker' in local_path:
            return 'photomaker'
        elif any(x in local_path for x in ['classifiers', 'classifier']):
            return 'classifiers'
        elif 'diffusers' in local_path:
            return 'diffusers'
        elif 'rembg' in local_path:
            return 'rembg'
        
        # Common custom node model directories
        elif any(x in local_path for x in
                 ['ipadapter', 'ip_adapter', 'ip-adapter']):
            return 'ipadapter'
        elif any(x in local_path for x in
                 ['animatediff', 'motion_module', 'motion-module']):
            return 'animatediff'
        elif any(x in local_path for x in
                 ['insightface', 'face_analysis', 'face-analysis']):
            return 'insightface'
        elif any(x in local_path for x in
                 ['instantid', 'instant_id', 'instant-id']):
            return 'instantid'
        elif 'inpaint' in local_path:
            return 'inpaint'
        elif any(x in local_path for x in ['segmentation', 'segment']):
            return 'segmentation'
        elif any(x in local_path for x in ['depth', 'depth_estimation']):
            return 'depth_estimation'
        elif any(x in local_path for x in
                 ['pose', 'pose_estimation', 'openpose']):
            return 'pose_estimation'
        elif any(x in local_path for x in ['video', 'video_models']):
            return 'video_models'
        elif any(x in local_path for x in ['audio', 'audio_models']):
            return 'audio_models'
        
        # Fallback for unknown types
        else:
            # extract the model type from the path
            extracted_type = self._determine_model_type_from_path(local_path)
            return extracted_type or "other"
    
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
            group = self._determine_model_type_from_path(local_path)
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
                                source: str = "internet",
                                sym_linked_from: str = None) -> bool:
        """Register a model downloaded from the internet
        (HuggingFace, CivitAI, etc.)"""
        try:
            group = self._determine_model_type_from_path(local_path)
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
            if sym_linked_from:
                model_object["symLinkedFrom"] = sym_linked_from
            
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
                                   model_type: str = None,
                                   model_name: str = None,
                                   sym_linked_from: str = None) -> bool:
        """Register a model downloaded from HuggingFace"""
        download_url = f"https://huggingface.co/{repo_id}"
        if filename:
            download_url += f"/blob/main/{filename}"
        
        if not model_name:
            model_name = (filename or
                          self._extract_model_name_from_path(local_path))
        
        # Call register_internet_model with all parameters
        group = self._determine_model_type_from_path(local_path)
        file_size = self._get_file_size(local_path)
        
        # Create model object for HuggingFace downloads
        model_object = {
            "localPath": local_path,
            "modelName": model_name,
            "directoryGroup": group,
            "downloadUrl": download_url,
            "downloadSource": "huggingface",
            "repositoryId": repo_id
        }
        
        # Add optional fields
        if file_size:
            model_object["modelSize"] = file_size
        if filename:
            model_object["fileName"] = filename
        if sym_linked_from:
            model_object["symLinkedFrom"] = sym_linked_from
        
        # Convert to JSON string
        model_json = json.dumps(model_object)
        
        # Create the command
        command = f"create_or_update_model '{group}' '{model_json}'"
        
        success, output = self._run_script_command(command)
        
        if success:
            logger.info(f"Successfully registered HuggingFace model: "
                        f"{local_path}")
            return True
        else:
            logger.error(f"Failed to register HuggingFace model: {output}")
            return False
    
    def register_civitai_model(self, local_path: str, model_id: str = None,
                               version_id: str = None,
                               direct_url: str = None,
                               model_type: str = None,
                               model_name: str = None,
                               sym_linked_from: str = None) -> bool:
        """Register a model downloaded from CivitAI"""
        if direct_url:
            download_url = direct_url
        elif model_id:
            download_url = f"https://civitai.com/models/{model_id}"
            if version_id:
                download_url += f"?modelVersionId={version_id}"
        else:
            download_url = "https://civitai.com"
        
        if not model_name:
            model_name = self._extract_model_name_from_path(local_path)
        
        # Call register_internet_model with extended functionality
        group = self._determine_model_type_from_path(local_path, model_type)
        file_size = self._get_file_size(local_path)
        
        # Create model object for CivitAI downloads
        model_object = {
            "localPath": local_path,
            "modelName": model_name,
            "directoryGroup": group,
            "downloadUrl": download_url,
            "downloadSource": "civitai"
        }
        
        # Add optional fields
        if file_size:
            model_object["modelSize"] = file_size
        if model_id:
            model_object["modelId"] = model_id
        if version_id:
            model_object["versionId"] = version_id
        if sym_linked_from:
            model_object["symLinkedFrom"] = sym_linked_from
        
        # Convert to JSON string
        model_json = json.dumps(model_object)
        
        # Create the command
        command = f"create_or_update_model '{group}' '{model_json}'"
        
        success, output = self._run_script_command(command)
        
        if success:
            logger.info(f"Successfully registered CivitAI model: "
                        f"{local_path}")
            return True
        else:
            logger.error(f"Failed to register CivitAI model: {output}")
            return False
    
    def register_google_drive_model(self, local_path: str, drive_url: str,
                                    model_type: str = None,
                                    model_name: str = None,
                                    sym_linked_from: str = None) -> bool:
        """Register a model downloaded from Google Drive"""
        if not model_name:
            model_name = self._extract_model_name_from_path(local_path)
        return self.register_internet_model(
            local_path=local_path,
            download_url=drive_url,
            model_name=model_name,
            model_type=model_type,
            source="google_drive",
            sym_linked_from=sym_linked_from
        )
    
    def register_direct_url_model(self, local_path: str, url: str,
                                  model_type: str = None,
                                  model_name: str = None,
                                  sym_linked_from: str = None) -> bool:
        """Register a model downloaded from a direct URL"""
        if not model_name:
            model_name = self._extract_model_name_from_path(local_path)
        return self.register_internet_model(
            local_path=local_path,
            download_url=url,
            model_name=model_name,
            model_type=model_type,
            source="direct_url",
            sym_linked_from=sym_linked_from
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

    def remove_model_by_path(self, local_path: str) -> bool:
        """Remove a model from the configuration by its local path
        
        This method removes both the model entry and any symlinks
        that reference the deleted file.
        
        Args:
            local_path: The local file path of the model to remove
            
        Returns:
            bool: True if removal was successful, False otherwise
        """
        try:
            # Determine the model group based on the path
            group = self._determine_model_group(local_path)
            
            # Extract model name from path
            model_name = self._extract_model_name_from_path(local_path)
            
            logger.info(f"Attempting to remove model: {local_path} "
                        f"(group: {group}, name: {model_name})")
            
            # Create the command to remove the model
            # The shell script should handle both model removal and
            # symlink cleanup
            command = f"remove_model_by_path '{local_path}'"
            
            success, output = self._run_script_command(command)
            
            if success:
                logger.info(f"Successfully removed model from config: "
                            f"{local_path}")
                return True
            else:
                # Log as warning rather than error since the file might not
                # have been tracked in the first place
                logger.warning(f"Could not remove model from config "
                               f"(may not have been tracked): {local_path}, "
                               f"output: {output}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing model from config: {local_path}, "
                         f"error: {e}")
            return False
    
    def get_model_info_by_path(self, local_path: str) -> Optional[dict]:
        """Get model information from the config by local path"""
        try:
            # Use shell script to find model by path
            command = f"find_model_by_path '{local_path}'"
            success, output = self._run_script_command(command)
            
            if success and output.strip():
                output = output.strip()
                
                # Check if output looks like a file path (temp file)
                if output.startswith('/') and not output.startswith('{'):
                    try:
                        # Try to read from the file
                        with open(output, 'r') as f:
                            json_content = f.read().strip()
                        if json_content:
                            model_info = json.loads(json_content)
                            print(f"Model info read from temp file: {model_info}")
                            return model_info
                    except (FileNotFoundError, json.JSONDecodeError) as e:
                        logger.warning(f"Failed to read temp file "
                                       f"{output}: {e}")
                        return None
                else:
                    try:
                        # Try to parse as direct JSON output
                        model_info = json.loads(output)
                        return model_info
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse model info JSON: {e}")
                        logger.debug(f"Raw output was: {repr(output)}")
                        return None
            else:
                logger.debug(f"Model not found in config: {local_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting model info by path: {e}")
            return None

    def register_symlink_model(self, source_path: str, symlink_path: str,
                               source_model_info: dict = None) -> bool:
        """Register a symlink model based on source model information"""
        try:
            # Get source model info if not provided
            if not source_model_info:
                source_model_info = self.get_model_info_by_path(source_path)
            
            # Determine the model group from the symlink path (destination)
            # This is important because the symlink should be registered
            # under the group where it's located, not where the source is
            symlink_model_type = self._determine_model_type_from_path(symlink_path)
            
            if not source_model_info:
                logger.warning(f"Source model not found in config: "
                               f"{source_path}")
                logger.warning("Cannot register symlink without source model "
                               "info. Symlink registration skipped.")
                return False
            
            # Determine the registration method based on source model type
            download_source = source_model_info.get("downloadSource",
                                                    "unknown")
            print(f"Registering symlink model from source: {download_source}, "
                  f"destination group: {symlink_model_type}")
            
            # Create symlink model entry based on source model
            # Use symlink_model_type for all registrations
            if download_source == "s3":
                return self.register_s3_model(
                    local_path=symlink_path,
                    s3_path=source_model_info.get("originalS3Path", ""),
                    model_name=source_model_info.get("modelName"),
                    model_type=symlink_model_type,  # Use destination group
                    download_link=source_model_info.get("downloadUrl"),
                    sym_linked_from=source_path
                )
            elif download_source == "huggingface":
                return self.register_huggingface_model(
                    local_path=symlink_path,
                    repo_id=source_model_info.get("repositoryId", ""),
                    filename=source_model_info.get("fileName"),
                    model_name=source_model_info.get("modelName"),
                    model_type=symlink_model_type,  # Use destination group
                    sym_linked_from=source_path
                )
            elif download_source == "civitai":
                return self.register_civitai_model(
                    local_path=symlink_path,
                    model_id=source_model_info.get("modelId"),
                    model_name=source_model_info.get("modelName"),
                    model_type=symlink_model_type,  # Use destination group
                    sym_linked_from=source_path
                )
            elif download_source == "google_drive":
                return self.register_google_drive_model(
                    local_path=symlink_path,
                    drive_url=source_model_info.get("googleDriveUrl", ""),
                    model_name=source_model_info.get("modelName"),
                    model_type=symlink_model_type,  # Use destination group
                    sym_linked_from=source_path
                )
            elif download_source == "direct_url":
                return self.register_direct_url_model(
                    local_path=symlink_path,
                    url=source_model_info.get("downloadUrl", ""),
                    model_name=source_model_info.get("modelName"),
                    model_type=symlink_model_type,  # Use destination group
                    sym_linked_from=source_path
                )
            else:
                # Fallback to internet model registration
                download_url = source_model_info.get("downloadUrl",
                                                     "manual_symlink")
                return self.register_internet_model(
                    local_path=symlink_path,
                    download_url=download_url,
                    model_name=source_model_info.get("modelName"),
                    model_type=symlink_model_type,  # Use destination group
                    sym_linked_from=source_path
                )
                
        except Exception as e:
            logger.error(f"Error registering symlink model: {e}")
            return False


# Global instance
model_config_manager = ModelConfigManager()
