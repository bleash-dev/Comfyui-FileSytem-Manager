import asyncio
import json
from aiohttp import web
from ..missing_models_handler import missing_model_handler, missing_model_progress_store, MissingModelProgressTracker
from ..shared_state import download_cancellation_flags

def setup_missing_models_routes(routes):
    """Setup missing models related routes"""
    
    @routes.post('/filesystem/download_missing_model')
    async def download_missing_model(request):
        """Download a missing model by searching HF and CivitAI"""
        try:
            data = await request.json()
            model_name = data.get('model_name')
            node_type = data.get('node_type')
            field_name = data.get('field_name')  # Added field_name parameter
            session_id = data.get('session_id')
            
            if not model_name:
                return web.json_response({
                    "success": False,
                    "error": "Model name is required"
                }, status=400)
            
            # Start the download in background
            loop = asyncio.get_event_loop()
            loop.create_task(missing_model_handler.download_missing_model(
                model_name=model_name,
                node_type=node_type,
                session_id=session_id,
                field_name=field_name  # Pass field_name to the handler
            ))
            
            return web.json_response({
                "success": True,
                "message": "Download started",
                "session_id": session_id
            })
            
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    @routes.get('/filesystem/missing_model_progress/{session_id}')
    async def get_missing_model_progress(request):
        """Get progress for missing model download"""
        session_id = request.match_info.get('session_id')
        
        if not session_id:
            return web.json_response({
                "status": "error",
                "message": "Session ID is required",
                "percentage": 0
            }, status=400)
        
        progress = missing_model_progress_store.get(session_id, {
            "status": "not_found",
            "message": "Download session not found",
            "percentage": 0
        })
        
        return web.json_response(progress)

    @routes.post('/filesystem/cancel_missing_model_download')
    async def cancel_missing_model_download(request):
        """Cancel a missing model download"""
        try:
            data = await request.json()
            session_id = data.get('session_id')
            
            if not session_id:
                return web.json_response({
                    "success": False,
                    "error": "Session ID is required"
                }, status=400)
            
            # Set cancellation flag
            download_cancellation_flags[session_id] = True
            
            # Update progress
            MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
            
            return web.json_response({
                "success": True,
                "message": "Download cancellation requested"
            })
            
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    @routes.post('/filesystem/get_community_link')
    async def get_community_link(request):
        """Get community support link for failed model downloads"""
        try:
            data = await request.json()
            model_name = data.get('model_name', '')
            error_logs = data.get('error_logs', '')
            runpod_id = data.get('runpod_id', '')
            
            community_link = await missing_model_handler.get_community_link(
                model_name=model_name,
                error_logs=error_logs,
                runpod_id=runpod_id
            )
            
            return web.json_response({
                "success": True,
                "community_link": community_link
            })
            
        except Exception as e:
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
