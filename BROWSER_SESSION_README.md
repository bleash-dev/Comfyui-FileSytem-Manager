# Shared Browser Session Manager

This module provides a persistent browser session manager for ComfyUI File System Manager, enabling reusable authentication across Google Drive and Hugging Face handlers.

## Overview

The `SharedBrowserSessionManager` is a singleton class that maintains persistent browser sessions with authentication data, eliminating the need to reauthenticate for every request.

## Features

- **Persistent Sessions**: Browser session data is stored in `$ComfyUI/.browser-session/`
- **Automatic Authentication**: Handles login for Google Drive and Hugging Face
- **Session Persistence**: Stores cookies, localStorage, sessionStorage, and IndexedDB data
- **Shared Contexts**: Both handlers use the same authenticated browser contexts
- **Resource Management**: Automatic cleanup and session state saving

## Directory Structure

```
$ComfyUI/.browser-session/
├── google_drive/
│   └── session_state.json
└── huggingface/
    └── session_state.json
```

## Usage

### Basic Usage

```python
from shared_browser_session import SharedBrowserSessionManager

# Initialize the session manager (singleton)
session_manager = SharedBrowserSessionManager()

# Ensure authentication for a service
await session_manager.ensure_authenticated('huggingface')
await session_manager.ensure_authenticated('google_drive')

# Create a page using the authenticated context
page = await session_manager.create_page('huggingface')
await page.goto('https://huggingface.co/some-restricted-repo')

# Use the page for your operations...

# Clean up
await page.close()
await session_manager.save_session_state('huggingface')
```

### In Handlers

#### Hugging Face Handler Update

```python
class BrowserAutomation:
    def __init__(self):
        self.screenshot_manager = ScreenshotManager()
        self.session_manager = SharedBrowserSessionManager()

    async def check_hf_access_with_playwright(self, hf_url: str, session_id: str = None):
        try:
            # Ensure authentication first
            await self.session_manager.ensure_authenticated('huggingface')
            
            # Create a page using the shared session
            page = await self.session_manager.create_page('huggingface')
            
            try:
                # Your existing logic here...
                has_access, error_msg = await self._check_repository_access_after_login(page, hf_url, session_id)
                return has_access, True, error_msg
            finally:
                await page.close()
                await self.session_manager.save_session_state('huggingface')
        except Exception as e:
            return False, True, f"Browser automation error: {str(e)}"
```

#### Google Drive Handler Update

```python
class GoogleDriveDownloaderAPI:
    def __init__(self):
        self.comfyui_base = folder_paths.base_path
        self.session_manager = SharedBrowserSessionManager()

    async def download_with_playwright(self, file_id, download_path, progress_callback=None, session_id=None):
        try:
            # Ensure authentication first
            await self.session_manager.ensure_authenticated('google_drive')
            
            # Create a page using the shared session
            page = await self.session_manager.create_page('google_drive')
            
            try:
                # Your existing download logic here...
                # The page is already authenticated to Google Drive
                pass
            finally:
                await page.close()
                await self.session_manager.save_session_state('google_drive')
        except Exception as e:
            print(f"Google Drive download error: {e}")
            return False, None, None
```

## Environment Variables

Set these environment variables for automatic authentication:

```bash
# Hugging Face
export HF_USERNAME="your_hf_username"
export HF_PASSWORD="your_hf_password"

# Google Drive
export GOOGLE_EMAIL="your_google_email@gmail.com"
export GOOGLE_PASSWORD="your_google_password"
```

## API Reference

### SharedBrowserSessionManager

#### Methods

- `get_context(service: str, **context_options) -> BrowserContext`
  - Get or create a persistent browser context for a service
  - Services: 'google_drive' or 'huggingface'

- `create_page(service: str, **page_options) -> Page`
  - Create a new page in the service context

- `is_authenticated(service: str) -> bool`
  - Check if the service is already authenticated

- `ensure_authenticated(service: str, force_login: bool = False) -> bool`
  - Ensure a service is authenticated, login if necessary

- `login_google_drive(email: str = None, password: str = None) -> bool`
  - Login to Google Drive

- `login_huggingface(username: str = None, password: str = None) -> bool`
  - Login to Hugging Face

- `save_session_state(service: str)`
  - Save the current session state for a service

- `cleanup_context(service: str)`
  - Clean up a specific context

- `cleanup_all()`
  - Clean up all browser resources

## Benefits

### Before (Without Shared Sessions)
- Each request creates a new browser instance
- Must authenticate every time
- No session persistence
- Higher resource usage
- Slower operations

### After (With Shared Sessions)
- Single browser instance shared across handlers
- Authentication persists across requests
- Session data stored and reused
- Lower resource usage
- Faster operations after initial authentication

## Session Data Stored

The following data is persisted:

- **Cookies**: Authentication tokens and session cookies
- **Local Storage**: User preferences and temporary data
- **Session Storage**: Session-specific data
- **IndexedDB**: Complex client-side database storage
- **Browser History**: Navigation history (optional)

## Error Handling

The session manager includes robust error handling:

- Graceful fallback if session data is corrupted
- Automatic cleanup on errors
- Session recreation if contexts become invalid
- Comprehensive logging for debugging

## Testing

Run the test script to verify functionality:

```bash
cd /path/to/ComfyUI/custom_nodes/Comfyui-FileSytem-Manager
python test_shared_browser_session.py
```

## Migration Guide

### From Existing Handlers

1. Import the session manager:
   ```python
   from .shared_browser_session import SharedBrowserSessionManager
   ```

2. Initialize in your class:
   ```python
   def __init__(self):
       self.session_manager = SharedBrowserSessionManager()
   ```

3. Replace `async with async_playwright()` with:
   ```python
   page = await self.session_manager.create_page('service_name')
   ```

4. Add cleanup:
   ```python
   finally:
       await page.close()
       await self.session_manager.save_session_state('service_name')
   ```

## Troubleshooting

### Session Data Issues
- Delete `$ComfyUI/.browser-session/` to reset all sessions
- Check file permissions on the session directory
- Verify environment variables are set correctly

### Authentication Problems
- Ensure credentials are correct in environment variables
- Check if 2FA is enabled (not currently supported)
- Verify network connectivity

### Performance Issues
- Check browser resource usage
- Consider calling `cleanup_all()` periodically
- Monitor session directory size

## Security Considerations

- Session files contain authentication data
- Ensure proper file permissions on session directory
- Consider encryption for sensitive deployments
- Regularly rotate authentication credentials
