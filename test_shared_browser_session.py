#!/usr/bin/env python3
"""
Test script to demonstrate the shared browser session manager for ComfyUI File System Manager.
"""
import asyncio
import os
from pathlib import Path
import sys

# Add the ComfyUI path to sys.path for imports
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared_browser_session import SharedBrowserSessionManager


async def test_browser_session_manager():
    """Test the shared browser session manager"""
    print("🧪 Testing Shared Browser Session Manager")
    
    # Initialize the session manager
    session_manager = SharedBrowserSessionManager()
    
    try:
        # Test 1: Check if Hugging Face authentication exists
        print("\n📋 Test 1: Check existing HuggingFace authentication")
        hf_authenticated = await session_manager.is_authenticated('huggingface')
        print(f"HuggingFace authenticated: {hf_authenticated}")
        
        # Test 2: Check if Google Drive authentication exists
        print("\n📋 Test 2: Check existing Google Drive authentication")
        gd_authenticated = await session_manager.is_authenticated('google_drive')
        print(f"Google Drive authenticated: {gd_authenticated}")
        
        # Test 3: Get browser contexts
        print("\n📋 Test 3: Create browser contexts")
        hf_context = await session_manager.get_context('huggingface')
        print(f"HuggingFace context created: {hf_context}")
        
        gd_context = await session_manager.get_context('google_drive')
        print(f"Google Drive context created: {gd_context}")
        
        # Test 4: Create pages
        print("\n📋 Test 4: Create pages using contexts")
        hf_page = await session_manager.create_page('huggingface')
        await hf_page.goto('https://huggingface.co/')
        print(f"HuggingFace page title: {await hf_page.title()}")
        await hf_page.close()
        
        gd_page = await session_manager.create_page('google_drive')
        await gd_page.goto('https://drive.google.com/')
        print(f"Google Drive page title: {await gd_page.title()}")
        await gd_page.close()
        
        # Test 5: Save session states
        print("\n📋 Test 5: Save session states")
        await session_manager.save_session_state('huggingface')
        await session_manager.save_session_state('google_drive')
        print("Session states saved")
        
        # Test 6: Check session directory
        print("\n📋 Test 6: Check session directory structure")
        session_dir = session_manager.session_dir
        print(f"Session directory: {session_dir}")
        
        if session_dir.exists():
            print("Session directory contents:")
            for item in session_dir.iterdir():
                if item.is_dir():
                    print(f"  📁 {item.name}/")
                    for subitem in item.iterdir():
                        print(f"    📄 {subitem.name}")
                else:
                    print(f"  📄 {item.name}")
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await session_manager.cleanup_all()
        print("\n🧹 Cleanup completed")


async def test_authentication():
    """Test authentication methods"""
    print("\n🔐 Testing Authentication Methods")
    
    session_manager = SharedBrowserSessionManager()
    
    try:
        # Check environment variables
        hf_username = os.environ.get("HF_USERNAME")
        hf_password = os.environ.get("HF_PASSWORD")
        google_email = os.environ.get("GOOGLE_EMAIL")
        google_password = os.environ.get("GOOGLE_PASSWORD")
        
        print(f"HF_USERNAME set: {'✅' if hf_username else '❌'}")
        print(f"HF_PASSWORD set: {'✅' if hf_password else '❌'}")
        print(f"GOOGLE_EMAIL set: {'✅' if google_email else '❌'}")
        print(f"GOOGLE_PASSWORD set: {'✅' if google_password else '❌'}")
        
        # Test HuggingFace authentication if credentials are available
        if hf_username and hf_password:
            print("\n🤗 Testing HuggingFace authentication...")
            hf_auth_result = await session_manager.ensure_authenticated('huggingface')
            print(f"HuggingFace authentication result: {'✅' if hf_auth_result else '❌'}")
        else:
            print("\n⚠️ HuggingFace credentials not found, skipping authentication test")
        
        # Test Google Drive authentication if credentials are available
        if google_email and google_password:
            print("\n🔍 Testing Google Drive authentication...")
            gd_auth_result = await session_manager.ensure_authenticated('google_drive')
            print(f"Google Drive authentication result: {'✅' if gd_auth_result else '❌'}")
        else:
            print("\n⚠️ Google Drive credentials not found, skipping authentication test")
    
    except Exception as e:
        print(f"\n❌ Authentication test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await session_manager.cleanup_all()


if __name__ == "__main__":
    print("🚀 Starting Shared Browser Session Manager Tests")
    
    # Run basic functionality tests
    asyncio.run(test_browser_session_manager())
    
    # Run authentication tests if credentials are available
    if any(os.environ.get(var) for var in ["HF_USERNAME", "HF_PASSWORD", "GOOGLE_EMAIL", "GOOGLE_PASSWORD"]):
        asyncio.run(test_authentication())
    else:
        print("\n⚠️ No authentication credentials found in environment variables")
        print("Set HF_USERNAME/HF_PASSWORD and/or GOOGLE_EMAIL/GOOGLE_PASSWORD to test authentication")
    
    print("\n🎉 All tests completed!")
