#!/usr/bin/env python3
"""
Workflow Execution Integration for ComfyUI File System Manager
Provides API endpoints to start and track workflow executions
"""

import os
import json
import uuid
import time
import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

# Global execution tracking
workflow_executions = {}


class WorkflowExecutionAPI:
    """API for managing ComfyUI workflow executions"""
    
    def __init__(self):
        # Try to import ComfyUI server components
        try:
            from server import PromptServer
            self.prompt_server = PromptServer.instance
            self.server_available = True
        except ImportError:
            logger.warning("ComfyUI server not available for workflow execution")
            self.prompt_server = None
            self.server_available = False
    
    def generate_execution_id(self) -> str:
        """Generate a unique execution ID"""
        return str(uuid.uuid4())
    
    def validate_workflow(self, workflow_json: Dict[str, Any]) -> tuple[bool, str]:
        """Validate workflow JSON structure"""
        try:
            # Basic validation - check if it has the required ComfyUI structure
            if not isinstance(workflow_json, dict):
                return False, "Workflow must be a JSON object"
            
            # Check for nodes structure (basic ComfyUI workflow format)
            if not workflow_json:
                return False, "Workflow cannot be empty"
            
            # More specific validation could be added here
            # For now, we'll accept any non-empty dict as a valid workflow
            return True, "Workflow validation passed"
            
        except Exception as e:
            return False, f"Workflow validation error: {str(e)}"
    
    async def start_workflow_execution(self, workflow_json: Dict[str, Any], 
                                     client_id: str = None) -> Dict[str, Any]:
        """Start workflow execution and return execution ID"""
        try:
            # Generate execution ID
            execution_id = self.generate_execution_id()
            
            # Validate workflow
            is_valid, validation_message = self.validate_workflow(workflow_json)
            if not is_valid:
                return {
                    "success": False,
                    "error": validation_message,
                    "message": "Workflow validation failed"
                }
            
            # Check if server is available
            if not self.server_available:
                return {
                    "success": False,
                    "error": "ComfyUI server not available",
                    "message": "Cannot execute workflow - server not initialized"
                }
            
            # Initialize execution tracking
            workflow_executions[execution_id] = {
                "status": "queued",
                "workflow": workflow_json,
                "client_id": client_id,
                "created_at": time.time(),
                "started_at": None,
                "completed_at": None,
                "progress": 0,
                "current_node": None,
                "error": None,
                "outputs": {},
                "execution_time": None
            }
            
            # Queue the workflow for execution
            try:
                # This mimics how ComfyUI handles prompt execution
                prompt_data = {
                    "prompt": workflow_json,
                    "client_id": client_id or execution_id
                }
                
                # Add to execution queue (this would integrate with ComfyUI's execution system)
                await self._queue_workflow_execution(execution_id, prompt_data)
                
                # Update status to queued
                workflow_executions[execution_id]["status"] = "queued"
                
                return {
                    "success": True,
                    "execution_id": execution_id,
                    "status": "queued",
                    "message": "Workflow queued for execution successfully",
                    "created_at": workflow_executions[execution_id]["created_at"]
                }
                
            except Exception as e:
                # Clean up tracking on queue failure
                if execution_id in workflow_executions:
                    del workflow_executions[execution_id]
                
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Failed to queue workflow for execution"
                }
                
        except Exception as e:
            logger.error(f"Error starting workflow execution: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Exception occurred while starting workflow execution"
            }
    
    async def _queue_workflow_execution(self, execution_id: str, 
                                      prompt_data: Dict[str, Any]):
        """Queue workflow for execution with ComfyUI server"""
        try:
            if self.prompt_server and hasattr(self.prompt_server, 'send_sync'):
                # This is a simplified version - actual implementation would depend on
                # ComfyUI's internal API structure
                
                # Start execution asynchronously
                asyncio.create_task(
                    self._execute_workflow_async(execution_id, prompt_data)
                )
            else:
                raise RuntimeError("ComfyUI server is not available for execution")
                
        except Exception as e:
            logger.error(f"Error queuing workflow {execution_id}: {e}")
            raise
    
    async def _execute_workflow_async(self, execution_id: str, 
                                    prompt_data: Dict[str, Any]):
        """Execute workflow asynchronously"""
        try:
            # Update status to running
            if execution_id in workflow_executions:
                workflow_executions[execution_id]["status"] = "running"
                workflow_executions[execution_id]["started_at"] = time.time()
            
            # Here you would integrate with ComfyUI's actual execution system
            # This is a placeholder that simulates the execution process
            
            workflow = prompt_data["prompt"]
            total_nodes = len(workflow) if workflow else 1
            
            # Simulate node-by-node execution
            for i, (node_id, node_data) in enumerate(workflow.items()):
                if execution_id not in workflow_executions:
                    return  # Execution was cancelled
                
                # Update progress
                progress = int((i / total_nodes) * 100)
                workflow_executions[execution_id]["progress"] = progress
                workflow_executions[execution_id]["current_node"] = node_id
                
                # Simulate processing time
                await asyncio.sleep(0.5)
            
            # Mark as completed
            if execution_id in workflow_executions:
                workflow_executions[execution_id]["status"] = "completed"
                workflow_executions[execution_id]["completed_at"] = time.time()
                workflow_executions[execution_id]["progress"] = 100
                workflow_executions[execution_id]["current_node"] = None
                
                # Calculate execution time
                start_time = workflow_executions[execution_id]["started_at"]
                end_time = workflow_executions[execution_id]["completed_at"]
                workflow_executions[execution_id]["execution_time"] = end_time - start_time
                
        except Exception as e:
            logger.error(f"Error executing workflow {execution_id}: {e}")
            if execution_id in workflow_executions:
                workflow_executions[execution_id]["status"] = "failed"
                workflow_executions[execution_id]["error"] = str(e)
                workflow_executions[execution_id]["completed_at"] = time.time()
    
    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get the status of a workflow execution"""
        try:
            if execution_id not in workflow_executions:
                return {
                    "success": False,
                    "error": "Execution ID not found",
                    "message": f"No execution found with ID: {execution_id}"
                }
            
            execution_data = workflow_executions[execution_id]
            
            # Calculate runtime if still running
            runtime = None
            if execution_data["started_at"]:
                if execution_data["completed_at"]:
                    runtime = execution_data["completed_at"] - execution_data["started_at"]
                else:
                    runtime = time.time() - execution_data["started_at"]
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": execution_data["status"],
                "progress": execution_data["progress"],
                "current_node": execution_data["current_node"],
                "created_at": execution_data["created_at"],
                "started_at": execution_data["started_at"],
                "completed_at": execution_data["completed_at"],
                "execution_time": execution_data.get("execution_time"),
                "runtime": runtime,
                "error": execution_data["error"],
                "has_outputs": bool(execution_data["outputs"]),
                "message": f"Execution {execution_data['status']}"
            }
            
        except Exception as e:
            logger.error(f"Error getting execution status for {execution_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Exception occurred while getting execution status"
            }
    
    def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """Cancel a workflow execution"""
        try:
            if execution_id not in workflow_executions:
                return {
                    "success": False,
                    "error": "Execution ID not found",
                    "message": f"No execution found with ID: {execution_id}"
                }
            
            execution_data = workflow_executions[execution_id]
            
            if execution_data["status"] in ["completed", "failed", "cancelled"]:
                return {
                    "success": False,
                    "error": "Cannot cancel completed execution",
                    "message": f"Execution is already {execution_data['status']}"
                }
            
            # Mark as cancelled
            workflow_executions[execution_id]["status"] = "cancelled"
            workflow_executions[execution_id]["completed_at"] = time.time()
            workflow_executions[execution_id]["error"] = "Cancelled by user"
            
            return {
                "success": True,
                "execution_id": execution_id,
                "status": "cancelled",
                "message": "Execution cancelled successfully"
            }
            
        except Exception as e:
            logger.error(f"Error cancelling execution {execution_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Exception occurred while cancelling execution"
            }
    
    def list_executions(self, limit: int = 50) -> Dict[str, Any]:
        """List recent workflow executions"""
        try:
            # Sort by creation time (most recent first)
            sorted_executions = sorted(
                workflow_executions.items(),
                key=lambda x: x[1]["created_at"],
                reverse=True
            )
            
            # Limit results
            limited_executions = sorted_executions[:limit]
            
            # Prepare response data
            executions_list = []
            for execution_id, execution_data in limited_executions:
                executions_list.append({
                    "execution_id": execution_id,
                    "status": execution_data["status"],
                    "progress": execution_data["progress"],
                    "created_at": execution_data["created_at"],
                    "started_at": execution_data["started_at"],
                    "completed_at": execution_data["completed_at"],
                    "execution_time": execution_data.get("execution_time"),
                    "has_error": bool(execution_data["error"]),
                    "has_outputs": bool(execution_data["outputs"])
                })
            
            return {
                "success": True,
                "executions": executions_list,
                "total_count": len(workflow_executions),
                "returned_count": len(executions_list),
                "message": f"Retrieved {len(executions_list)} executions"
            }
            
        except Exception as e:
            logger.error(f"Error listing executions: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Exception occurred while listing executions"
            }
    
    def cleanup_old_executions(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """Clean up old execution records"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            old_executions = []
            for execution_id, execution_data in list(workflow_executions.items()):
                age = current_time - execution_data["created_at"]
                if age > max_age_seconds:
                    old_executions.append(execution_id)
                    del workflow_executions[execution_id]
            
            return {
                "success": True,
                "cleaned_count": len(old_executions),
                "remaining_count": len(workflow_executions),
                "max_age_hours": max_age_hours,
                "message": f"Cleaned up {len(old_executions)} old executions"
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up executions: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Exception occurred while cleaning up executions"
            }


# Global instance
workflow_execution_api = WorkflowExecutionAPI()
