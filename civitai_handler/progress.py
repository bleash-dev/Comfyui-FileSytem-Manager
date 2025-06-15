import time

# Global progress tracking for CivitAI downloads
civitai_progress_store = {}

class ProgressTracker:
    @staticmethod
    def update_progress(session_id: str, message: str, percentage: int, status: str = "progress"):
        """Update progress for a session"""
        if session_id:
            civitai_progress_store[session_id] = {
                "status": status, 
                "message": message, 
                "percentage": percentage
            }
            print(f"🔄 CivitAI Progress Update - Session: {session_id}, Percentage: {percentage}%, Message: {message}")

    @staticmethod
    def set_completed(session_id: str, message: str):
        """Mark session as completed"""
        if session_id:
            civitai_progress_store[session_id] = {
                "status": "completed", 
                "message": message, 
                "percentage": 100
            }
            print(f"✅ CivitAI Completed - Session: {session_id}, Message: {message}")

    @staticmethod
    def set_error(session_id: str, message: str):
        """Mark session as error"""
        if session_id:
            civitai_progress_store[session_id] = {
                "status": "error", 
                "message": message, 
                "percentage": 0
            }
            print(f"❌ CivitAI Error - Session: {session_id}, Message: {message}")

    @staticmethod
    def set_access_restricted(session_id: str, message: str):
        """Mark session as access restricted"""
        if session_id:
            civitai_progress_store[session_id] = {
                "status": "access_restricted", 
                "message": message, 
                "percentage": 0
            }
            print(f"🔒 CivitAI Access Restricted - Session: {session_id}, Message: {message}")

    @staticmethod
    def set_cancelled(session_id: str, message: str):
        """Mark session as cancelled"""
        if session_id:
            civitai_progress_store[session_id] = {
                "status": "cancelled", 
                "message": message, 
                "percentage": 0
            }
            print(f"🚫 CivitAI Cancelled - Session: {session_id}, Message: {message}")
