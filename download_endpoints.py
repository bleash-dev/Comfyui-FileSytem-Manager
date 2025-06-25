import os
import sys
import zipfile
import tempfile
from pathlib import Path
from typing import List
import asyncio

try:
    import aiofiles
    import aiofiles.os
except ImportError:
    print("aiofiles not found. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiofiles>=23.1.0"])
    import aiofiles
    import aiofiles.os

import folder_paths
from server import PromptServer
from aiohttp import web, hdrs
from aiohttp.web_response import StreamResponse

class FileSystemDownloadAPI:
    """File system download endpoints for ComfyUI"""
    
    def __init__(self):
        # Get ComfyUI base path
        self.base_path = folder_paths.base_path # Corrected base path
    
    def _validate_path(self, file_path: str) -> tuple[bool, str]:
        """Validate file path for security"""
        if not file_path:
            return False, "No file path provided"
        
        # Security check - ensure path is within ComfyUI directory
        full_path = os.path.join(self.base_path, file_path)
        full_path = os.path.normpath(full_path)
        
        if not full_path.startswith(self.base_path):
            return False, "Access denied"
        
        return True, full_path
    
    async def download_file(self, request):
        """Download a single file"""
        try:
            file_path = request.query.get('path', '')
            is_valid, result = self._validate_path(file_path)
            
            if not is_valid:
                return web.json_response({'error': result}, status=400 if "No file path" in result else 403)
            
            full_path = result
            
            if not await aiofiles.os.path.exists(full_path):
                return web.json_response({'error': 'File not found'}, status=404)
            
            if not await aiofiles.os.path.isfile(full_path):
                return web.json_response({'error': 'Path is not a file'}, status=400)
            
            # Get file info
            filename = os.path.basename(full_path)
            file_size = (await aiofiles.os.stat(full_path)).st_size
            
            # Create response with proper headers
            response = StreamResponse(
                status=200,
                headers={
                    hdrs.CONTENT_TYPE: 'application/octet-stream',
                    hdrs.CONTENT_DISPOSITION: f'attachment; filename="{filename}"',
                    hdrs.ACCESS_CONTROL_ALLOW_HEADERS: "*",
                    hdrs.ACCESS_CONTROL_ALLOW_METHODS: "*",
                    hdrs.ACCESS_CONTROL_ALLOW_ORIGIN: "*",
                    hdrs.CONTENT_LENGTH: str(file_size)
                }
            )
            
            await response.prepare(request)
            
            # Stream file content
            async with aiofiles.open(full_path, 'rb') as f:
                while True:
                    chunk = await f.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    await response.write(chunk)
            
            await response.write_eof()
            return response
            
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def download_multiple_files(self, request):
        """Download multiple files as a zip archive"""
        try:
            data = await request.json()
            file_paths = data.get('paths', [])
            
            if not file_paths:
                return web.json_response({'error': 'No file paths provided'}, status=400)
            
            # Validate all paths
            valid_files = []
            for file_path in file_paths:
                is_valid, result = self._validate_path(file_path)
                if not is_valid:
                    continue
                
                full_path = result
                if await aiofiles.os.path.exists(full_path) and await aiofiles.os.path.isfile(full_path):
                    valid_files.append((file_path, full_path))
            
            if not valid_files:
                return web.json_response({'error': 'No valid files found'}, status=404)
            
            # Create temporary zip file
            temp_dir = tempfile.gettempdir()
            zip_filename = f"files_{len(valid_files)}_items.zip"
            temp_zip_path = os.path.join(temp_dir, zip_filename)
            
            # Create zip file
            await self._create_zip_file(valid_files, temp_zip_path)
            
            # Get zip file size
            zip_size = (await aiofiles.os.stat(temp_zip_path)).st_size
            
            # Create response
            response = StreamResponse(
                status=200,
                headers={
                    hdrs.CONTENT_TYPE: 'application/zip',
                    hdrs.CONTENT_DISPOSITION: f'attachment; filename="{zip_filename}"',
                    hdrs.CONTENT_LENGTH: str(zip_size)
                }
            )
            
            await response.prepare(request)
            
            # Stream zip file content
            async with aiofiles.open(temp_zip_path, 'rb') as f:
                while True:
                    chunk = await f.read(8192)
                    if not chunk:
                        break
                    await response.write(chunk)
            
            await response.write_eof()
            
            # Clean up temporary file
            try:
                os.unlink(temp_zip_path)
            except:
                pass  # Best effort cleanup
            
            return response
            
        except Exception as e:
            print(f"Error creating zip download: {str(e)}")
            return web.json_response({'error': str(e)}, status=500)

    async def _create_zip_file(self, file_list: List[tuple], zip_path: str):
        """Create a zip file from a list of (relative_path, full_path) tuples"""
        def _create_zip():
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for relative_path, full_path in file_list:
                    # Use the relative path structure in the zip
                    # This preserves the directory structure
                    arcname = relative_path.replace('\\', '/')  # Normalize path separators
                    zipf.write(full_path, arcname)
        
        # Run in thread to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _create_zip)
