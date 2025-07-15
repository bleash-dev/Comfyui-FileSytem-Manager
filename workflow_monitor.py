import os
import json
from pathlib import Path
from typing import Dict, List, Set, Optional
import subprocess

import folder_paths
from server import PromptServer
from aiohttp import web


try:
    from .global_models_manager import GlobalModelsManager
    global_models_manager = GlobalModelsManager()
except ImportError:
    print("Global models manager not available for workflow monitoring")
    global_models_manager = None


class WorkflowMonitor:
    def __init__(self):
        self.comfyui_base = Path(folder_paths.base_path)
        self.models_dir = self.comfyui_base / "models"
        self.last_workflow_hash = None
        self.monitoring_enabled = True
        self.auto_download_enabled = True
        self.missing_models = set()
        self.model_categories = self._get_model_categories()
        self.aws_configured = self._check_aws_configuration()
        
    def _check_aws_configuration(self):
        """Check if AWS CLI is configured"""
        try:
            result = subprocess.run(['aws', 's3', 'ls'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False

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
        
    def _get_model_categories(self) -> List[str]:
        """Get all model categories from folder_paths"""
        # Standard ComfyUI model folders based on folder_paths.py and nodes.py
        standard_categories = [
            # Core ComfyUI model directories from folder_paths.py
            'checkpoints', 'configs', 'loras', 'vae', 'vae_approx',
            'text_encoders', 'diffusion_models', 'clip_vision',
            'style_models', 'embeddings', 'diffusers', 'controlnet',
            'gligen', 'upscale_models', 'hypernetworks', 'photomaker',
            'classifiers',
            
            # Legacy/alternate names for compatibility
            'clip', 'unet', 't2i_adapter',
            
            # Common custom node model directories
            'ipadapter', 'animatediff', 'insightface', 'instantid',
            'inpaint', 'segmentation', 'depth_estimation',
            'pose_estimation', 'video_models', 'audio_models',
            
            # System directories
            'custom_nodes', 'sonic', 'other'
        ]

        # Add from folder_paths if available
        if hasattr(folder_paths, 'folder_names_and_paths'):
            for category in folder_paths.folder_names_and_paths.keys():
                if category not in standard_categories:
                    standard_categories.append(category)

        return standard_categories
    
    def extract_model_paths_from_workflow(self, workflow_data: dict) -> Set[str]:
        """Extract all model paths referenced in a workflow with precise path matching"""
        model_paths = set()
        
        def extract_from_node_recursive(node_data, path=""):
            if isinstance(node_data, dict):
                # Check if this is a node with inputs
                if 'inputs' in node_data:
                    inputs = node_data['inputs']
                    node_class = node_data.get('class_type', '')
                    
                    # Extract models based on node class and input patterns
                    for input_key, input_value in inputs.items():
                        if isinstance(input_value, str) and input_value:
                            model_path = self._extract_model_path_from_input(
                                input_key, input_value, node_class
                            )
                            if model_path:
                                model_paths.add(model_path)
                
                # Recursively check all dictionary values
                for key, value in node_data.items():
                    extract_from_node_recursive(value, f"{path}.{key}" if path else key)
                    
            elif isinstance(node_data, list):
                for i, item in enumerate(node_data):
                    extract_from_node_recursive(item, f"{path}[{i}]" if path else f"[{i}]")
        
        # Handle both old and new workflow formats
        if 'nodes' in workflow_data:
            # New format with nodes array
            for node in workflow_data['nodes']:
                extract_from_node_recursive(node)
        else:
            # Old format where each key is a node
            for node_id, node_data in workflow_data.items():
                if isinstance(node_data, dict):
                    extract_from_node_recursive(node_data)
        
        return model_paths
    
    def _extract_model_path_from_input(self, input_key: str, input_value: str, node_class: str) -> Optional[str]:
        """Extract model path from a specific input field"""
        if not input_value or not isinstance(input_value, str):
            return None
            
        # Clean the input value
        model_name = input_value.strip()
        if not model_name:
            return None
        
        # Skip if it's clearly not a model file
        if any(skip in model_name.lower() for skip in ['none', 'default', 'auto', 'random']):
            return None
        
        # If the path already includes a category (contains '/'), use it as-is
        if '/' in model_name:
            # Validate that it starts with a known category
            category = model_name.split('/')[0]
            if category in self.model_categories:
                return model_name
            else:
                # Try to map to a known category
                mapped_category = self._map_to_category(input_key, node_class)
                if mapped_category:
                    return f"{mapped_category}/{model_name}"
        
        # Determine category from input field name and node class
        category = self._determine_category_from_context(input_key, node_class, model_name)
        if category:
            return f"{category}/{model_name}"
        
        return None
    
    def _determine_category_from_context(self, input_key: str, node_class: str, model_name: str) -> Optional[str]:
        """Determine model category from input context"""
        input_lower = input_key.lower()
        node_lower = node_class.lower()
        model_lower = model_name.lower()
        
        # Direct field name mapping
        field_mappings = {
            'ckpt_name': 'checkpoints',
            'checkpoint_name': 'checkpoints', 
            'model_name': 'checkpoints',
            'lora_name': 'loras',
            'lora_model_name': 'loras',
            'vae_name': 'vae',
            'vae_': 'vae',
            'control_net_name': 'controlnet',
            'controlnet_name': 'controlnet',
            'upscale_model_name': 'upscale_models',
            'embedding_name': 'embeddings',
            'clip_name': 'clip',
            'clip_vision': 'clip_vision',
            'text_encoder': 'text_encoders',
            'diffusion_model': 'diffusion_models',
            'hypernetwork': 'hypernetworks',
            'style_model': 'style_models',
            'gligen': 'gligen',
            'photomaker': 'photomaker',
            'sonic': 'sonic'
        }
        
        # Check direct field mappings first
        for field_pattern, category in field_mappings.items():
            if field_pattern in input_lower:
                return category
        
        # Node class based mapping
        node_mappings = {
            'checkpoint': 'checkpoints',
            'lora': 'loras', 
            'controlnet': 'controlnet',
            'vae': 'vae',
            'upscale': 'upscale_models',
            'embedding': 'embeddings',
            'clip': 'clip',
            'diffusion': 'diffusion_models',
            'hypernetwork': 'hypernetworks',
            'style': 'style_models',
            'gligen': 'gligen',
            'photomaker': 'photomaker'
        }
        
        for node_pattern, category in node_mappings.items():
            if node_pattern in node_lower:
                return category
        
        # File extension based fallback
        if any(ext in model_lower for ext in ['.safetensors', '.ckpt', '.pt', '.pth']):
            # Try to determine from file characteristics
            if any(term in model_lower for term in ['lora', 'lycoris']):
                return 'loras'
            elif any(term in model_lower for term in ['vae', 'autoencoder']):
                return 'vae'
            elif any(term in model_lower for term in ['control', 'canny', 'depth', 'pose']):
                return 'controlnet'
            elif any(term in model_lower for term in ['upscale', 'esrgan', 'real']):
                return 'upscale_models'
            else:
                # Default to checkpoints for unknown .safetensors/.ckpt files
                return 'checkpoints'
        
        return None
    
    def _map_to_category(self, input_key: str, node_class: str) -> Optional[str]:
        """Map input context to model category"""
        return self._determine_category_from_context(input_key, node_class, "")
    
    def check_missing_models(self, model_paths: Set[str]) -> Set[str]:
        """Check which models are missing locally, considering exact paths"""
        missing = set()
        
        for model_path in model_paths:
            # Check exact path first
            local_path = self.models_dir / model_path
            if not local_path.exists():
                missing.add(model_path)
                continue
            
            # If it's a directory, check if it has content
            if local_path.is_dir() and not any(local_path.iterdir()):
                missing.add(model_path)
        
        return missing
    
    async def get_available_global_models(self, missing_models: Set[str]) -> Dict[str, dict]:
        """Check which missing models are available in global storage with full info"""
        if not global_models_manager or not self.aws_configured:
            return {}
            
        available = {}
        
        try:
            global_structure = await global_models_manager.get_global_models_structure()
            
            for model_path in missing_models:
                parts = model_path.split('/', 1)
                if len(parts) != 2:
                    available[model_path] = {'available': False}
                    continue
                    
                category, model_name = parts
                
                if category in global_structure:
                    if model_name in global_structure[category]:
                        model_info = global_structure[category][model_name]
                        if isinstance(model_info, dict) and model_info.get('type') == 'file':
                            available[model_path] = {
                                'available': True,
                                'type': model_info.get('type', 'file'),
                                'size': model_info.get('size', 0),
                                's3_path': model_info.get('s3_path', ''),
                                'local_path': str(self.models_dir / model_path)
                            }
                        else:
                            available[model_path] = {'available': False}
                    else:
                        available[model_path] = {'available': False}
                else:
                    available[model_path] = {'available': False}
                    
        except Exception as e:
            print(f"Error checking global models availability: {e}")
            
        return available
    
    async def auto_download_missing_models(self, missing_models: Set[str]) -> Dict[str, str]:
        """Download only missing models that are available globally"""
        if not global_models_manager or not self.auto_download_enabled or not self.aws_configured:
            return {}
            
        download_results = {}
        available_models = await self.get_available_global_models(missing_models)
        
        for model_path, model_info in available_models.items():
            if model_info.get('available', False):
                # Check once more if model still missing (might have been downloaded by another process)
                local_path = self.models_dir / model_path
                if local_path.exists():
                    download_results[model_path] = "already_exists"
                    print(f"⏭️ Skipping {model_path}: already exists locally")
                    continue
                
                try:
                    print(f"🔄 Auto-downloading missing model: {model_path}")
                    
                    # Use the existing global models manager download method
                    success = await global_models_manager.download_model(model_path)
                    
                    if success:
                        download_results[model_path] = "downloaded"
                        print(f"✅ Successfully downloaded: {model_path}")
                    else:
                        download_results[model_path] = "failed: download unsuccessful"
                        print(f"❌ Failed to download {model_path}")
                        
                except Exception as e:
                    download_results[model_path] = f"error: {str(e)}"
                    print(f"❌ Error downloading {model_path}: {e}")
            else:
                download_results[model_path] = "not_available"
                
        return download_results
    
    async def analyze_workflow(self, workflow_data: dict) -> Dict:
        """Analyze workflow and return comprehensive model status"""
        # Extract model paths with precise path matching
        model_paths = self.extract_model_paths_from_workflow(workflow_data)
        
        # Check which are missing locally
        missing_models = self.check_missing_models(model_paths)
        
        # Update instance state
        self.missing_models = missing_models
        
        # Get detailed availability info from global storage
        available_global = await self.get_available_global_models(missing_models)
        
        # Auto-download if enabled
        download_results = {}
        if self.auto_download_enabled and missing_models:
            download_results = await self.auto_download_missing_models(missing_models)
            
        # Separate available vs unavailable models
        available_for_download = {
            path: info for path, info in available_global.items() 
            if info.get('available', False)
        }
        unavailable_models = {
            path: info for path, info in available_global.items() 
            if not info.get('available', False)
        }
        
        return {
            "total_models": len(model_paths),
            "missing_models": len(missing_models),
            "available_for_download": len(available_for_download),
            "unavailable_models": len(unavailable_models),
            "model_paths": list(model_paths),
            "missing_list": list(missing_models),
            "available_models": available_for_download,
            "unavailable_list": list(unavailable_models.keys()),
            "global_availability": {path: info.get('available', False) for path, info in available_global.items()},
            "download_results": download_results,
            "auto_download_enabled": self.auto_download_enabled
        }
    
    def get_workflow_hash(self, workflow_data: dict) -> str:
        """Generate hash for workflow to detect changes"""
        import hashlib
        workflow_str = json.dumps(workflow_data, sort_keys=True)
        return hashlib.md5(workflow_str.encode()).hexdigest()


# Global workflow monitor instance
workflow_monitor = WorkflowMonitor()


# API Endpoints
@PromptServer.instance.routes.post("/filesystem/analyze_workflow")
async def analyze_workflow(request):
    """Analyze a workflow for missing models"""
    try:
        data = await request.json()
        workflow_data = data.get('workflow')
        
        if not workflow_data:
            return web.json_response({
                "success": False,
                "error": "No workflow data provided"
            }, status=400)
        
        analysis = await workflow_monitor.analyze_workflow(workflow_data)
        
        return web.json_response({
            "success": True,
            "analysis": analysis
        })

    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)


@PromptServer.instance.routes.post("/filesystem/auto_download_missing")
async def auto_download_missing(request):
    """Manually trigger auto-download of missing models"""
    try:
        if not workflow_monitor.missing_models:
            return web.json_response({
                "success": True,
                "message": "No missing models to download",
                "download_results": {}
            })
        
        download_results = await workflow_monitor.auto_download_missing_models(
            workflow_monitor.missing_models
        )
        
        return web.json_response({
            "success": True,
            "download_results": download_results
        })

    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)


@PromptServer.instance.routes.get("/filesystem/workflow_monitor_status")
async def get_monitor_status(request):
    """Get workflow monitor status"""
    try:
        return web.json_response({
            "success": True,
            "status": {
                "monitoring_enabled": workflow_monitor.monitoring_enabled,
                "auto_download_enabled": workflow_monitor.auto_download_enabled,
                "missing_models_count": len(workflow_monitor.missing_models),
                "missing_models": list(workflow_monitor.missing_models)
            }
        })

    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)


@PromptServer.instance.routes.post("/filesystem/toggle_auto_download")
async def toggle_auto_download(request):
    """Toggle auto-download feature"""
    try:
        data = await request.json()
        enabled = data.get('enabled', True)
        
        workflow_monitor.auto_download_enabled = enabled
        
        return web.json_response({
            "success": True,
            "auto_download_enabled": enabled
        })
        
    except Exception as e:
        return web.json_response({
            "success": False,
            "error": str(e)
        }, status=500)
