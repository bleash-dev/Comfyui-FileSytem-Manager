#!/usr/bin/env python3
"""
Sync Manager Integration for ComfyUI File System Manager
Integrates with the sync_manager.sh script to provide sync operations via API
"""

import os
import subprocess
import logging
import asyncio
from typing import Dict, Any

# Set up logging
logger = logging.getLogger(__name__)


class SyncManagerAPI:
    """Integration class for the sync manager shell script"""
    
    def __init__(self):
        self.network_volume = os.environ.get('NETWORK_VOLUME', '/workspace')
        self.script_path = f"{self.network_volume}/scripts/sync_manager.sh"
        
        logger.info(f"SyncManagerAPI initialized with script: "
                    f"{self.script_path}")
    
    def _run_sync_command(self, command: str,
                          timeout: int = 300) -> tuple[bool, str, str]:
        """Run a sync manager command"""
        try:
            # Build the full command
            full_command = f"bash {self.script_path} {command}"
            
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if success:
                logger.debug(f"Sync command succeeded: {command}")
            else:
                logger.error(f"Sync command failed: {command}, "
                             f"stderr: {stderr}")
            
            return success, stdout, stderr
                
        except subprocess.TimeoutExpired:
            logger.error(f"Sync command timed out: {command}")
            return False, "", "Command timed out"
        except Exception as e:
            logger.error(f"Error running sync command: {command}, "
                         f"error: {e}")
            return False, "", str(e)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get the current sync status"""
        try:
            success, stdout, stderr = self._run_sync_command("status")
            
            if success:
                return {
                    "success": True,
                    "status": "retrieved",
                    "output": stdout,
                    "message": "Sync status retrieved successfully"
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "error": stderr or "Failed to retrieve sync status",
                    "message": "Failed to get sync status"
                }
                
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "message": "Exception occurred while getting sync status"
            }
    
    def force_unlock_sync(self, sync_type: str = None) -> Dict[str, Any]:
        """Force unlock sync locks"""
        try:
            command = "unlock"
            if sync_type:
                command += f" {sync_type}"
            
            success, stdout, stderr = self._run_sync_command(command)
            
            if success:
                return {
                    "success": True,
                    "status": "unlocked",
                    "output": stdout,
                    "message": f"Successfully unlocked {sync_type or 'all'} sync locks"
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "error": stderr or "Failed to unlock sync",
                    "message": f"Failed to unlock {sync_type or 'all'} sync locks"
                }
                
        except Exception as e:
            logger.error(f"Error unlocking sync: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "message": "Exception occurred while unlocking sync"
            }
    
    def test_sync_lock(self, sync_type: str = "test_sync") -> Dict[str, Any]:
        """Test the sync lock mechanism"""
        try:
            command = f"test {sync_type}"
            success, stdout, stderr = self._run_sync_command(command, timeout=60)
            
            if success:
                return {
                    "success": True,
                    "status": "test_passed",
                    "output": stdout,
                    "message": f"Sync lock test passed for {sync_type}"
                }
            else:
                return {
                    "success": False,
                    "status": "test_failed",
                    "error": stderr or "Lock test failed",
                    "output": stdout,
                    "message": f"Sync lock test failed for {sync_type}"
                }
                
        except Exception as e:
            logger.error(f"Error testing sync lock: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "message": "Exception occurred while testing sync lock"
            }
    
    def run_sync(self, sync_type: str) -> Dict[str, Any]:
        """Run a specific sync operation"""
        valid_sync_types = [
            "user_data", "user_shared", "global_shared", 
            "user_assets", "logs"
        ]
        
        if sync_type not in valid_sync_types:
            return {
                "success": False,
                "status": "invalid_type",
                "error": f"Invalid sync type: {sync_type}",
                "valid_types": valid_sync_types,
                "message": "Please specify a valid sync type"
            }
        
        try:
            command = f"run {sync_type}"
            success, stdout, stderr = self._run_sync_command(command, timeout=600)
            
            if success:
                return {
                    "success": True,
                    "status": "completed",
                    "sync_type": sync_type,
                    "output": stdout,
                    "message": f"Successfully ran {sync_type} sync"
                }
            else:
                return {
                    "success": False,
                    "status": "failed",
                    "sync_type": sync_type,
                    "error": stderr or f"Failed to run {sync_type} sync",
                    "output": stdout,
                    "message": f"Failed to run {sync_type} sync"
                }
                
        except Exception as e:
            logger.error(f"Error running sync {sync_type}: {e}")
            return {
                "success": False,
                "status": "error",
                "sync_type": sync_type,
                "error": str(e),
                "message": f"Exception occurred while running {sync_type} sync"
            }
    
    def run_all_syncs(self) -> Dict[str, Any]:
        """Run all sync operations sequentially"""
        sync_types = ["user_data", "user_shared", "global_shared", 
                     "user_assets", "logs"]
        results = {}
        failed_syncs = []
        successful_syncs = []
        
        try:
            for sync_type in sync_types:
                logger.info(f"Running sync: {sync_type}")
                result = self.run_sync(sync_type)
                results[sync_type] = result
                
                if result["success"]:
                    successful_syncs.append(sync_type)
                else:
                    failed_syncs.append(sync_type)
            
            overall_success = len(failed_syncs) == 0
            
            return {
                "success": overall_success,
                "status": "completed" if overall_success else "partial_failure",
                "total_syncs": len(sync_types),
                "successful_syncs": successful_syncs,
                "failed_syncs": failed_syncs,
                "detailed_results": results,
                "message": (f"All syncs completed successfully" 
                           if overall_success else 
                           f"Completed with {len(failed_syncs)} failures")
            }
            
        except Exception as e:
            logger.error(f"Error running all syncs: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "partial_results": results,
                "message": "Exception occurred while running all syncs"
            }
    
    def list_sync_scripts(self) -> Dict[str, Any]:
        """List all available sync scripts"""
        try:
            success, stdout, stderr = self._run_sync_command("list")
            
            if success:
                return {
                    "success": True,
                    "status": "retrieved",
                    "output": stdout,
                    "available_syncs": [
                        "user_data", "user_shared", "global_shared",
                        "user_assets", "logs"
                    ],
                    "message": "Successfully retrieved sync scripts list"
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "error": stderr or "Failed to list sync scripts",
                    "message": "Failed to list sync scripts"
                }
                
        except Exception as e:
            logger.error(f"Error listing sync scripts: {e}")
            return {
                "success": False,
                "status": "error",
                "error": str(e),
                "message": "Exception occurred while listing sync scripts"
            }
    
    def get_sync_logs(self, sync_type: str, lines: int = 20) -> Dict[str, Any]:
        """Get logs for a specific sync type"""
        valid_sync_types = [
            "user_data", "user_shared", "global_shared",
            "user_assets", "logs"
        ]
        
        if sync_type not in valid_sync_types:
            return {
                "success": False,
                "status": "invalid_type",
                "error": f"Invalid sync type: {sync_type}",
                "valid_types": valid_sync_types,
                "message": "Please specify a valid sync type"
            }
        
        try:
            command = f"logs {sync_type} {lines}"
            success, stdout, stderr = self._run_sync_command(command)
            
            if success:
                return {
                    "success": True,
                    "status": "retrieved",
                    "sync_type": sync_type,
                    "lines_requested": lines,
                    "output": stdout,
                    "message": f"Successfully retrieved {sync_type} logs"
                }
            else:
                return {
                    "success": False,
                    "status": "error",
                    "sync_type": sync_type,
                    "error": stderr or f"Failed to get {sync_type} logs",
                    "message": f"Failed to retrieve {sync_type} logs"
                }
                
        except Exception as e:
            logger.error(f"Error getting sync logs for {sync_type}: {e}")
            return {
                "success": False,
                "status": "error",
                "sync_type": sync_type,
                "error": str(e),
                "message": f"Exception occurred while getting {sync_type} logs"
            }
    
    async def run_sync_async(self, sync_type: str) -> Dict[str, Any]:
        """Run a sync operation asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run_sync, sync_type)
    
    async def run_all_syncs_async(self) -> Dict[str, Any]:
        """Run all sync operations asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run_all_syncs)


# Global instance
sync_manager_api = SyncManagerAPI()
