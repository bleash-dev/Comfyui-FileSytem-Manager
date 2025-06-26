#!/usr/bin/env python3
"""
Browser Session Cleanup Utility for ComfyUI File System Manager

This utility helps manage and clean up browser session data.
"""
import asyncio
import shutil
from pathlib import Path
import sys
import argparse

# Add the ComfyUI path to sys.path for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    import folder_paths
    from shared_browser_session import SharedBrowserSessionManager
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the ComfyUI environment")
    sys.exit(1)


async def cleanup_all_sessions():
    """Clean up all browser sessions and data"""
    print("🧹 Cleaning up all browser sessions...")
    
    session_manager = SharedBrowserSessionManager()
    
    try:
        # Clean up running browser instances
        await session_manager.cleanup_all()
        print("✅ Browser instances cleaned up")
        
        # Remove session data directory
        session_dir = session_manager.session_dir
        if session_dir.exists():
            shutil.rmtree(session_dir)
            print(f"✅ Removed session directory: {session_dir}")
        else:
            print(f"ℹ️ Session directory doesn't exist: {session_dir}")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")


async def cleanup_service_session(service: str):
    """Clean up session data for a specific service"""
    print(f"🧹 Cleaning up {service} session...")
    
    session_manager = SharedBrowserSessionManager()
    
    try:
        # Clean up the specific context
        await session_manager.cleanup_context(service)
        
        # Remove service-specific session data
        if service == 'google_drive':
            session_path = session_manager.google_session_path
        elif service == 'huggingface':
            session_path = session_manager.huggingface_session_path
        else:
            print(f"❌ Unknown service: {service}")
            return
        
        if session_path.exists():
            shutil.rmtree(session_path)
            print(f"✅ Removed {service} session data: {session_path}")
        else:
            print(f"ℹ️ {service} session directory doesn't exist")
            
    except Exception as e:
        print(f"❌ Error cleaning up {service} session: {e}")


async def show_session_info():
    """Show information about current browser sessions"""
    print("📊 Browser Session Information")
    
    session_manager = SharedBrowserSessionManager()
    session_dir = session_manager.session_dir
    
    print(f"\nSession directory: {session_dir}")
    print(f"Directory exists: {'✅' if session_dir.exists() else '❌'}")
    
    if session_dir.exists():
        print("\nSession data:")
        
        # Check Google Drive session
        google_session = session_manager.google_session_path
        google_state_file = google_session / 'session_state.json'
        print(f"\n🔍 Google Drive:")
        print(f"  Directory: {google_session}")
        print(f"  Exists: {'✅' if google_session.exists() else '❌'}")
        print(f"  Session file: {'✅' if google_state_file.exists() else '❌'}")
        
        if google_state_file.exists():
            file_size = google_state_file.stat().st_size
            print(f"  Session file size: {file_size} bytes")
        
        # Check Hugging Face session
        hf_session = session_manager.huggingface_session_path
        hf_state_file = hf_session / 'session_state.json'
        print(f"\n🤗 Hugging Face:")
        print(f"  Directory: {hf_session}")
        print(f"  Exists: {'✅' if hf_session.exists() else '❌'}")
        print(f"  Session file: {'✅' if hf_state_file.exists() else '❌'}")
        
        if hf_state_file.exists():
            file_size = hf_state_file.stat().st_size
            print(f"  Session file size: {file_size} bytes")
        
        # Calculate total size
        total_size = 0
        for file_path in session_dir.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        print(f"\nTotal session data size: {total_size} bytes ({total_size / 1024:.1f} KB)")
    
    # Check if browser instances are running
    try:
        # Try to check authentication status (this will show if browsers are active)
        print("\n🔍 Checking active browser instances...")
        hf_auth = await session_manager.is_authenticated('huggingface')
        gd_auth = await session_manager.is_authenticated('google_drive')
        
        print(f"Hugging Face authenticated: {'✅' if hf_auth else '❌'}")
        print(f"Google Drive authenticated: {'✅' if gd_auth else '❌'}")
        
    except Exception as e:
        print(f"⚠️ Could not check authentication status: {e}")
    
    finally:
        await session_manager.cleanup_all()


async def reset_service_authentication(service: str):
    """Reset authentication for a specific service"""
    print(f"🔄 Resetting {service} authentication...")
    
    session_manager = SharedBrowserSessionManager()
    
    try:
        # First clean up existing session
        await cleanup_service_session(service)
        
        # Try to authenticate again
        print(f"🔐 Attempting to re-authenticate {service}...")
        auth_result = await session_manager.ensure_authenticated(service, force_login=True)
        
        if auth_result:
            print(f"✅ {service} authentication successful")
            await session_manager.save_session_state(service)
        else:
            print(f"❌ {service} authentication failed")
            
    except Exception as e:
        print(f"❌ Error resetting {service} authentication: {e}")
    
    finally:
        await session_manager.cleanup_all()


def main():
    parser = argparse.ArgumentParser(
        description="Browser Session Cleanup Utility for ComfyUI File System Manager"
    )
    parser.add_argument(
        "action",
        choices=["info", "cleanup", "cleanup-google", "cleanup-hf", "reset-google", "reset-hf"],
        help="Action to perform"
    )
    
    args = parser.parse_args()
    
    if args.action == "info":
        asyncio.run(show_session_info())
    elif args.action == "cleanup":
        asyncio.run(cleanup_all_sessions())
    elif args.action == "cleanup-google":
        asyncio.run(cleanup_service_session("google_drive"))
    elif args.action == "cleanup-hf":
        asyncio.run(cleanup_service_session("huggingface"))
    elif args.action == "reset-google":
        asyncio.run(reset_service_authentication("google_drive"))
    elif args.action == "reset-hf":
        asyncio.run(reset_service_authentication("huggingface"))


if __name__ == "__main__":
    print("🔧 Browser Session Cleanup Utility")
    print("=" * 50)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Done!")
