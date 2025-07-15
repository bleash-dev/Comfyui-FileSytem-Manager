#!/usr/bin/env python3
"""
Initial Models Sync System
Handles the initial synchronization of models from S3 when pod starts
"""

import os
import json
import subprocess
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)


class InitialModelsSyncManager:
    """Manager for initial models synchronization from S3"""
    
    def __init__(self):
        self.network_volume = os.environ.get('NETWORK_VOLUME', '/workspace')
        self.script_path = (f"{self.network_volume}/scripts/"
                            f"model_download_integration.sh")
        self.model_config_manager = None
        
        # Import model config manager if available
        try:
            from .model_config_integration import model_config_manager
            self.model_config_manager = model_config_manager
            logger.info("Model config manager loaded for initial sync")
        except ImportError:
            logger.warning("Model config manager not available")
        
        logger.info(f"InitialModelsSyncManager initialized with script: "
                    f"{self.script_path}")
        
    
    def _run_asynchronously(self, command: str):
        try:
            # Source the script and run the command
            full_command = f"source {self.script_path} && {command}"
            result = subprocess.run(
                ['bash', '-c', full_command],
                            )
            
            if result.returncode == 0:
                logger.debug(f"Shell command succeeded: {command}")
                return True
            else:
                logger.error(f"Shell command failed: {command}, "
                             f"stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Shell command timed out: {command}")
            return False, "Command timed out"
        except Exception as e:
            logger.error(f"Error running shell command: {command}, "
                         f"error: {e}")
            return False, str(e)
        

    
    def _run_shell_command(self, command: str) -> tuple[bool, str]:
        """Run a shell command and return success status and output"""
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
                logger.debug(f"Shell command succeeded: {command}")
                return True, result.stdout.strip()
            else:
                logger.error(f"Shell command failed: {command}, "
                             f"stderr: {result.stderr}")
                return False, result.stderr.strip()
                
        except subprocess.TimeoutExpired:
            logger.error(f"Shell command timed out: {command}")
            return False, "Command timed out"
        except Exception as e:
            logger.error(f"Error running shell command: {command}, "
                         f"error: {e}")
            return False, str(e)
    
    async def get_initial_models_list(self) -> Dict[str, Any]:
        """Get list of models that need initial sync from config"""
        try:
            if not self.model_config_manager:
                return {"error": "Model config manager not available"}
            
            # Get models from config that have originalS3Path but no local file
            success, output = self._run_shell_command("get_downloadable_models")
            
            if not success:
                logger.error(f"Failed to get models list: {output}")
                return {"error": f"Failed to get models: {output}"}
            
            try:
                all_models = json.loads(output)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse models JSON: {e}")
                return {"error": "Failed to parse models configuration"}
            
            # Filter models that need sync - now handling array format
            models_to_sync = {}
            total_size = 0
            
            for model_data in all_models:
                # Get group name from the model data
                group_name = (model_data.get('directoryGroup') or
                              model_data.get('groupName', 'Unknown'))
                model_name = model_data.get('modelName', 'Unknown')
                
                # Check if model has S3 path and local path doesn't exist
                original_s3_path = model_data.get('originalS3Path')
                local_path = model_data.get('localPath')
                model_size = model_data.get('modelSize', 0)
                
                if (original_s3_path and
                        local_path and
                        not os.path.exists(local_path)):
                    
                    # Initialize group if not exists
                    if group_name not in models_to_sync:
                        models_to_sync[group_name] = {}
                    
                    models_to_sync[group_name][model_name] = {
                        "modelName": model_name,
                        "originalS3Path": original_s3_path,
                        "localPath": local_path,
                        "modelSize": model_size,
                        "directoryGroup": group_name,
                        "downloadSource": model_data.get(
                            'downloadSource', 's3'),
                        "downloadUrl": model_data.get(
                            'downloadUrl', original_s3_path),
                        "status": "pending"
                    }
                    total_size += model_size
            
            return {
                "success": True,
                "models": models_to_sync,
                "totalModels": sum(len(group)
                                   for group in models_to_sync.values()),
                "totalSize": total_size,
                "formattedSize": self._format_file_size(total_size)
            }
            
        except Exception as e:
            logger.error(f"Error getting initial models list: {e}")
            return {"error": str(e)}
    
    async def start_sync_download(
            self, models_to_sync: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Start downloading selected models"""
        try:
            if not models_to_sync:
                return {"error": "No models specified for sync"}
            
            # Convert models list to the format expected by download system
            download_requests = []
            for model in models_to_sync:
                download_requests.append({
                    "directoryGroup": model["directoryGroup"],
                    "modelName": model["modelName"],
                    "originalS3Path": model["originalS3Path"],
                    "localPath": model["localPath"],
                    "modelSize": model.get("modelSize", 0)
                })
            
            # Use the shell script to start downloads
            models_json = json.dumps(download_requests)
            success = self._run_asynchronously(
                f'download_models "list" \'{models_json}\''
            )
            
            if success:
                # Extract progress file path from output
                return {
                    "success": True,
                    "message": "Download started successfully",
                    "modelsCount": len(models_to_sync)
                }
            else:
                return {"error": f"Failed to start download: {output}"}
                
        except Exception as e:
            logger.error(f"Error starting sync download: {e}")
            return {"error": str(e)}
    
    async def get_sync_progress(self) -> Dict[str, Any]:
        """Get current sync progress"""
        try:
            success, output = self._run_shell_command(
                "get_all_download_progress")
            
            if not success:
                return {"error": f"Failed to get progress: {output}"}
            
            # Parse progress file
            try:
                if os.path.exists(output.strip()):
                    with open(output.strip(), 'r') as f:
                        progress_data = json.load(f)
                    
                    # Calculate overall progress
                    total_models = 0
                    completed_models = 0
                    total_size = 0
                    downloaded_size = 0
                    
                    for group_name, group_models in progress_data.items():
                        for model_name, model_data in group_models.items():
                            total_models += 1
                            model_size = model_data.get('totalSize', 0)
                            model_downloaded = model_data.get('downloaded', 0)
                            
                            total_size += model_size
                            downloaded_size += model_downloaded
                            
                            if model_data.get('status') == 'completed':
                                completed_models += 1
                    
                    overall_progress = 0
                    if total_size > 0:
                        overall_progress = (downloaded_size / total_size) * 100
                    
                    return {
                        "success": True,
                        "progress": progress_data,
                        "summary": {
                            "totalModels": total_models,
                            "completedModels": completed_models,
                            "totalSize": total_size,
                            "downloadedSize": downloaded_size,
                            "overallProgress": round(overall_progress, 2),
                            "formattedTotalSize": self._format_file_size(
                                total_size),
                            "formattedDownloadedSize": self._format_file_size(
                                downloaded_size)
                        }
                    }
                else:
                    return {"success": True, "progress": {}, "summary": {}}
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse progress JSON: {e}")
                return {"error": "Failed to parse progress data"}
                
        except Exception as e:
            logger.error(f"Error getting sync progress: {e}")
            return {"error": str(e)}
    
    async def cancel_sync(
            self, model_path: Optional[str] = None) -> Dict[str, Any]:
        """Cancel sync downloads"""
        try:
            if model_path:
                # Cancel specific model
                success, output = self._run_shell_command(
                    f'cancel_download_by_path "{model_path}"'
                )
                message = f"Model download cancelled: {model_path}"
            else:
                # Cancel all downloads
                success, output = self._run_shell_command(
                    "cancel_all_downloads")
                message = "All downloads cancelled"
            
            if success:
                return {"success": True, "message": message}
            else:
                return {"error": f"Failed to cancel: {output}"}
                
        except Exception as e:
            logger.error(f"Error cancelling sync: {e}")
            return {"error": str(e)}
    
    async def remove_model_from_config(
            self, model_path: str) -> Dict[str, Any]:
        """Remove model from local configuration"""
        try:
            if not self.model_config_manager:
                return {"error": "Model config manager not available"}
            
            # Use the shell script to remove model
            success, output = self._run_shell_command(
                f'remove_model_by_path "{model_path}"'
            )
            
            if success:
                logger.info(f"Removed model from config: {model_path}")
                return {
                    "success": True,
                    "message": f"Model removed from configuration: "
                               f"{model_path}"
                }
            else:
                return {"error": f"Failed to remove model: {output}"}
                
        except Exception as e:
            logger.error(f"Error removing model from config: {e}")
            return {"error": str(e)}
    
    async def skip_initial_sync(self) -> Dict[str, Any]:
        """Mark initial sync as completed/skipped"""
        try:
            # Create a marker file to indicate sync was handled
            marker_file = os.path.join(
                self.network_volume,
                '.initial_sync_completed'
            )
            
            with open(marker_file, 'w') as f:
                json.dump({
                    "completed": True,
                    "timestamp": datetime.now().isoformat(),
                    "action": "skipped"
                }, f)
            
            return {
                "success": True,
                "message": "Initial sync marked as completed"
            }
            
        except Exception as e:
            logger.error(f"Error marking sync as completed: {e}")
            return {"error": str(e)}
    
    async def should_show_initial_sync(self) -> Dict[str, Any]:
        """Check if initial sync dialog should be shown and return models"""
        try:
            # Check if already completed/skipped
            marker_file = os.path.join(
                self.network_volume,
                '.initial_sync_completed'
            )
            
            if os.path.exists(marker_file):
                return {
                    "shouldShow": False,
                    "reason": "Initial sync already completed"
                }
            
            # Check if there are downloadable models
            models_result = await self.get_initial_models_list()
            
            if "error" in models_result:
                error_msg = models_result['error']
                logger.warning(f"Error checking downloadable models: "
                               f"{error_msg}")
                return {
                    "shouldShow": False,
                    "reason": f"Error checking models: {error_msg}"
                }
            
            # Return true only if there are models to sync
            has_models = models_result.get("totalModels", 0) > 0
            reason = ("Models available for sync" if has_models
                      else "No models need syncing")
            
            return {
                "shouldShow": has_models,
                "reason": reason,
                "models": models_result if has_models else None,
                "totalModels": models_result.get("totalModels", 0)
            }
            
        except Exception as e:
            logger.error(f"Error checking if should show initial sync: {e}")
            return {
                "shouldShow": False,
                "reason": f"Error: {str(e)}"
            }
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"


# Global instance
initial_sync_manager = InitialModelsSyncManager()
