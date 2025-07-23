import os
import asyncio
import aiohttp
import json
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import folder_paths
from .huggingface_handler.api import HuggingFaceDownloadAPI
from .civitai_handler.api import CivitAIDownloadAPI
from .shared_state import download_cancellation_flags
from .utils.nodes_not_path_mapping import get_directories_for_loader_class

# Import global models manager
try:
    from .global_models_manager import GlobalModelsManager, global_models_progress_store as global_progress_store
    GLOBAL_MODELS_AVAILABLE = True
    print("✅ Global models manager available for missing models")
except ImportError:
    GLOBAL_MODELS_AVAILABLE = False
    print("⚠️ Global models manager not available")

# Import model config manager
try:
    from .model_config_integration import model_config_manager
    MODEL_CONFIG_AVAILABLE = True
    print("✅ Model config manager available for registration")
except ImportError:
    MODEL_CONFIG_AVAILABLE = False
    model_config_manager = None
    print("⚠️ Model config manager not available")

# Add Google API import
try:
    from googleapi import google
    GOOGLE_API_AVAILABLE = True
    print("✅ Google API available for search")
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("⚠️ Google API not available. Install with: pip install googleapi")

# Add Playwright import for DuckDuckGo fallback
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
    print("✅ Playwright available for DuckDuckGo fallback")
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not available. DuckDuckGo fallback disabled")

# Global progress tracking for missing model downloads
missing_model_progress_store = {}

class MissingModelProgressTracker:
    @staticmethod
    def update_progress(session_id: str, message: str, percentage: int, status: str = "progress"):
        """Update progress for a missing model download session"""
        if session_id:
            missing_model_progress_store[session_id] = {
                "status": status,
                "message": message,
                "percentage": percentage
            }
            print(f"🔄 Missing Model Progress - Session: {session_id}, {percentage}%: {message}")

    @staticmethod
    def set_completed(session_id: str, message: str):
        """Mark session as completed"""
        if session_id:
            missing_model_progress_store[session_id] = {
                "status": "completed",
                "message": message,
                "percentage": 100
            }

    @staticmethod
    def set_error(session_id: str, message: str):
        """Mark session as error"""
        if session_id:
            missing_model_progress_store[session_id] = {
                "status": "error",
                "message": message,
                "percentage": 0
            }

    @staticmethod
    def set_cancelled(session_id: str, message: str):
        """Mark session as cancelled"""
        if session_id:
            missing_model_progress_store[session_id] = {
                "status": "cancelled",
                "message": message,
                "percentage": 0
            }

class MissingModelHandler:
    def __init__(self):
        self.hf_api = HuggingFaceDownloadAPI()
        self.civitai_api = CivitAIDownloadAPI()
        self.comfyui_base = folder_paths.base_path
        
        # Initialize global models manager if available
        if GLOBAL_MODELS_AVAILABLE:
            self.global_models_manager = GlobalModelsManager()
        else:
            self.global_models_manager = None

    def infer_model_directory(self, model_name: str, node_type: str = None) -> str:
        """Infer the model directory based on model name and node type"""
        model_name_lower = model_name.lower()
        
        # Node type based inference (primary)
        if node_type:
            node_type_lower = node_type.lower()
            if 'lora' in node_type_lower:
                return "models/loras"
            elif 'vae' in node_type_lower:
                return "models/vae"
            elif 'controlnet' in node_type_lower:
                return "models/controlnet"
            elif 'upscale' in node_type_lower:
                return "models/upscale_models"
            elif 'clip' in node_type_lower:
                return "models/clip"
            elif 'embedding' in node_type_lower:
                return "models/embeddings"
            elif 'checkpoint' in node_type_lower:
                return "models/checkpoints"
            elif 'diffusion' in node_type_lower:
                return "models/diffusion_models"
            elif 'textual' in node_type_lower:
                return "models/textual_inversion"
            elif 'safety' in node_type_lower:
                return "models/safety_checker"
            elif 'sampler' in node_type_lower:
                return "models/samplers"
            elif 'scheduler' in node_type_lower:
                return "models/schedulers"
            elif 'tokenizer' in node_type_lower:
                return "models/tokenizers"
            elif 'unet' in node_type_lower:
                return "models/unet"
            else:
                return "models/checkpoints"  # Default for unknown node types
        
        # Filename pattern based inference (fallback)
        if any(keyword in model_name_lower for keyword in ['lora', 'lyco']):
            return "models/loras"
        elif any(keyword in model_name_lower for keyword in ['vae']):
            return "models/vae"
        elif any(keyword in model_name_lower for keyword in ['controlnet', 'control_net']):
            return "models/controlnet"
        elif any(keyword in model_name_lower for keyword in ['upscal', 'esrgan']):
            return "models/upscale_models"
        elif any(keyword in model_name_lower for keyword in ['clip']):
            return "models/clip"
        elif any(keyword in model_name_lower for keyword in ['embedding', 'textual']):
            return "models/embeddings"
        elif any(keyword in model_name_lower for keyword in ['unet']):
            return "models/unet"
        elif any(keyword in model_name_lower for keyword in ['safety']):
            return "models/safety_checker"
        elif any(keyword in model_name_lower for keyword in ['sampler']):
            return "models/samplers"
        elif any(keyword in model_name_lower for keyword in ['scheduler']):
            return "models/schedulers"
        elif any(keyword in model_name_lower for keyword in ['tokenizer']):
            return "models/tokenizers"
        elif any(keyword in model_name_lower for keyword in ['diffusion']):
            return "models/diffusion_models"
        
        # Default fallback
        return "models/checkpoints"

    def _determine_model_type_from_path(self, directory_path: str) -> str:
        """Determine model type from the target directory path.
        
        Extracts the directory immediately after 'models/' in the path.
        Falls back to keyword-based detection if path structure doesn't match.
        """
        from pathlib import Path
        
        # Normalize the path
        path = Path(directory_path)
        parts = [part.lower() for part in path.parts]
        
        # Try to find 'models' in the path and get the next directory
        try:
            models_index = parts.index('models')
            if models_index + 1 < len(parts):
                model_type = parts[models_index + 1]
                # Map common variations to standard types
                type_mapping = {
                    'checkpoints': 'checkpoint',
                    'loras': 'lora',
                    'lora': 'lora',
                    'vae': 'vae',
                    'controlnet': 'controlnet',
                    'embeddings': 'embedding',
                    'upscale_models': 'upscale',
                    'upscale': 'upscale',
                    'clip': 'clip',
                    'unet': 'unet',
                    'ipadapter': 'ipadapter',
                    'clip_vision': 'clip_vision',
                    'style_models': 'style_models',
                    'diffusers': 'diffusers'
                }
                return type_mapping.get(model_type, model_type)
        except ValueError:
            # 'models' not found in path, fall back to keyword detection
            return model_type

    async def duckduckgo_search(self, query: str) -> List[str]:
        """
        Performs a search on DuckDuckGo's simple HTML version,
        prints the results for logging, and returns a list of clean, direct URLs.
        
        Returns an empty list if no results are found or an error occurs.
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠️ Playwright not available, cannot perform DuckDuckGo search")
            return []
            
        results_list = []  # 1. Initialize an empty list
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        print(f"[INFO] Performing DDG Search: {search_url}")

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=False)  # Use headless for production
                page = await browser.new_page()
                await page.goto(search_url, timeout=60000)

                links = await page.locator("a.result__a").all()

                if not links:
                    print("[WARNING] No search results found.")
                    return [] # Return empty list on no results

                print("\n[RESULTS] (Printed from within the function)")
                for i, link_element in enumerate(links[:10]):  # Get more results
                    redirect_url = await link_element.get_attribute("href")
                    title = await link_element.inner_text()
                    
                    try:
                        parsed_url = urllib.parse.urlparse(redirect_url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        
                        if 'uddg' in query_params:
                            clean_url = query_params['uddg'][0]
                        else:
                            clean_url = redirect_url
                    
                    except (KeyError, IndexError):
                        clean_url = redirect_url

                    print(f"{i+1}. {title}\n   {clean_url}")
                    results_list.append(clean_url) # 2. Append the clean URL to the list
                
                return results_list # 3. Return the populated list

            except Exception as e:
                print(f"[ERROR] DuckDuckGo search failed: {e}")
                return [] # Return empty list on error
            finally:
                # Ensure browser is closed even if an unexpected error occurs
                if browser and browser.is_connected():
                    await browser.close()

    async def search_huggingface_with_duckduckgo(self, model_name: str, session_id: str = None) -> Optional[Dict]:
        """Search for model on Hugging Face using DuckDuckGo search as fallback"""
        try:
            MissingModelProgressTracker.update_progress(session_id, f"Searching DuckDuckGo for '{model_name}' on Hugging Face...", 25)
            
            # Create search query targeting Hugging Face
            search_query = f"{model_name} site:huggingface.co"
            
            print(f"🔍 DuckDuckGo search query: {search_query}")
            
            # Perform DuckDuckGo search
            search_results = await self.duckduckgo_search(search_query)
            
            if not search_results:
                print(f"❌ No DuckDuckGo search results found for '{model_name}'")
                return None
            
            print(f"🔍 Found {len(search_results)} DuckDuckGo search results")
            
            # Process search results to find exact matches
            for url in search_results:
                if not url or 'huggingface.co' not in url:
                    continue
                
                print(f"🔗 Processing URL: {url}")
                # Parse the Hugging Face URL
                hf_info = self._parse_huggingface_url(url, model_name)
                if hf_info and hf_info.get('relevance_score', 0) > 10:  # Only high relevance matches
                    print(f"✅ Found relevant HF result: {url} (relevance: {hf_info.get('relevance_score', 0)})")
                    hf_info['search_method'] = 'duckduckgo'
                    return hf_info
            
            print(f"❌ No relevant Hugging Face results found for '{model_name}' on DuckDuckGo")
            return None
                
        except Exception as e:
            print(f"Error in DuckDuckGo search for Hugging Face: {e}")
            return None

    async def search_civitai_with_duckduckgo(self, model_name: str, session_id: str = None) -> Optional[Dict]:
        """Search for model on CivitAI using DuckDuckGo search as fallback"""
        try:
            MissingModelProgressTracker.update_progress(session_id, f"Searching DuckDuckGo for '{model_name}' on CivitAI...", 45)
            
            # Create search query targeting CivitAI
            search_query = f"{model_name} site:civitai.com"
            
            print(f"🔍 DuckDuckGo search query for CivitAI: {search_query}")
            
            # Perform DuckDuckGo search
            search_results = await self.duckduckgo_search(search_query)
            
            if not search_results:
                print(f"❌ No DuckDuckGo search results found for '{model_name}' on CivitAI")
                return None
            
            print(f"🔍 Found {len(search_results)} CivitAI DuckDuckGo search results")
            
            # Process search results to find exact matches
            for url in search_results:
                if not url or 'civitai.com' not in url:
                    continue
                
                # Parse the CivitAI URL
                civitai_info = self._parse_civitai_url(url, model_name)
                if civitai_info and civitai_info.get('relevance_score', 0) > 5:  # Only relevant matches
                    print(f"✅ Found relevant CivitAI result: {url} (relevance: {civitai_info.get('relevance_score', 0)})")
                    civitai_info['search_method'] = 'duckduckgo'
                    return civitai_info
            
            print(f"❌ No relevant CivitAI results found for '{model_name}' on DuckDuckGo")
            return None
                
        except Exception as e:
            print(f"Error in DuckDuckGo search for CivitAI: {e}")
            return None
    
    def _calculate_hf_relevance_score(self, repo_id: str, filename: str, model_name: str) -> float:
        """Calculate relevance score for Hugging Face results"""
        score = 0.0
        model_name_lower = model_name.lower()
        
        # Highest priority: exact filename match
        if filename:
            filename_lower = filename.lower()
            filename_base = filename_lower.rsplit('.', 1)[0] if '.' in filename_lower else filename_lower
            
            if model_name_lower == filename_lower:
                score += 50.0  # Exact match with extension
            elif model_name_lower == filename_base:
                score += 45.0  # Exact match without extension
            elif model_name_lower in filename_lower:
                score += 20.0  # Partial match in filename
        
        # Second priority: repo name match
        repo_name = repo_id.split('/')[-1].lower()
        if model_name_lower in repo_name:
            score += 15.0
            if model_name_lower == repo_name:
                score += 10.0
        
        return score
        
    def _parse_huggingface_url(self, url: str, model_name: str) -> Optional[Dict]:
        """Parse Hugging Face URL and calculate relevance"""
        try:
            if not url or 'huggingface.co' not in url:
                return None
            
            # Extract repo information from URL
            url_pattern = r'huggingface\.co/([^/]+/[^/?]+)'
            match = re.search(url_pattern, url)
            
            if not match:
                return None
                
            repo_id = match.group(1)
            
            # Check if it's a file URL
            is_file_url = '/blob/' in url or '/resolve/' in url or '/blame/' in url
            filename = None
            
            if is_file_url:
                file_pattern = r'/(?:blob|blame|resolve)/[^/]+/(.+?)(?:\?|$)'
                file_match = re.search(file_pattern, url)
                if file_match:
                    filename = file_match.group(1)
            
            # Calculate relevance score
            relevance_score = self._calculate_hf_relevance_score(repo_id, filename, model_name)
            
            return {
                "source": "huggingface",
                "repo_id": repo_id,
                "filename": filename,
                "url": url,
                "relevance_score": relevance_score,
                "search_method": "google_api"
            }
            
        except Exception as e:
            print(f"Error parsing Hugging Face URL: {e}")
            return None

    async def search_huggingface_with_google(self, model_name: str, session_id: str = None) -> Optional[Dict]:
        """Search for model on Hugging Face using Google search with DuckDuckGo fallback"""
        # Try Google API first
        if GOOGLE_API_AVAILABLE:
            try:
                MissingModelProgressTracker.update_progress(session_id, f"Searching Google for '{model_name}' on Hugging Face...", 25)
                
                # Create search query targeting Hugging Face with exact model name
                search_query = f'{model_name} from huggingface'
                print(f"🔍 Google search query: {search_query}")
                
                # Perform Google search
                search_results = []
                try:
                    search_results = google.search(search_query, 1)
                except Exception as search_error:
                    print(f"❌ Google search failed: {search_error}")
                    # Fall back to DuckDuckGo
                    return await self.search_huggingface_with_duckduckgo(model_name, session_id)
                
                print(f"🔍 Found {len(search_results)} Google search results")
                
                # Process search results to find exact matches
                for url in search_results:
                    if not url or 'huggingface.co' not in url:
                        continue
                    
                    print(f"🔗 Processing URL: {url}")
                    # Parse the Hugging Face URL
                    hf_info = self._parse_huggingface_url(url, model_name)
                    if hf_info and hf_info.get('relevance_score', 0) > 10:  # Only high relevance matches
                        print(f"✅ Found relevant HF result: {url} (relevance: {hf_info.get('relevance_score', 0)})")
                        hf_info['search_method'] = 'google_api'
                        return hf_info
                
                print(f"❌ No relevant Hugging Face results found for '{model_name}' on Google")
                # Fall back to DuckDuckGo
                return await self.search_huggingface_with_duckduckgo(model_name, session_id)
                
            except Exception as e:
                print(f"Error in Google search for Hugging Face: {e}")
                # Fall back to DuckDuckGo
                return await self.search_huggingface_with_duckduckgo(model_name, session_id)
        else:
            print("⚠️ Google API not available, using DuckDuckGo directly")
            return await self.search_huggingface_with_duckduckgo(model_name, session_id)

    async def search_civitai_with_google(self, model_name: str, session_id: str = None) -> Optional[Dict]:
        """Search for model on CivitAI using Google search with DuckDuckGo fallback"""
        # Try Google API first
        if GOOGLE_API_AVAILABLE:
            try:
                MissingModelProgressTracker.update_progress(session_id, f"Searching Google for '{model_name}' on CivitAI...", 45)
                
                # Create search query targeting CivitAI with exact model name
                search_query = f'"{model_name}" site:civitai.com'
                print(f"🔍 Google search query for CivitAI: {search_query}")
                
                # Perform Google search
                search_results = []
                try:
                    search_urls = google.search(search_query, 1)
                    search_results = list(search_urls)
                except Exception as search_error:
                    print(f"❌ Google search for CivitAI failed: {search_error}")
                    # Fall back to DuckDuckGo
                    return await self.search_civitai_with_duckduckgo(model_name, session_id)
                
                print(f"🔍 Found {len(search_results)} CivitAI Google search results")
                
                # Process search results to find exact matches
                for url in search_results:
                    if not url or 'civitai.com' not in url:
                        continue
                    
                    # Parse the CivitAI URL
                    civitai_info = self._parse_civitai_url(url, model_name)
                    if civitai_info and civitai_info.get('relevance_score', 0) > 5:  # Only relevant matches
                        print(f"✅ Found relevant CivitAI result: {url} (relevance: {civitai_info.get('relevance_score', 0)})")
                        civitai_info['search_method'] = 'google_api'
                        return civitai_info
                
                print(f"❌ No relevant CivitAI results found for '{model_name}' on Google")
                # Fall back to DuckDuckGo
                return await self.search_civitai_with_duckduckgo(model_name, session_id)
                
            except Exception as e:
                print(f"Error in Google search for CivitAI: {e}")
                # Fall back to DuckDuckGo
                return await self.search_civitai_with_duckduckgo(model_name, session_id)
        else:
            print("⚠️ Google API not available, using DuckDuckGo directly")
            return await self.search_civitai_with_duckduckgo(model_name, session_id)
    
    def _parse_civitai_url(self, url: str, model_name: str) -> Optional[Dict]:
        """Parse CivitAI URL and calculate relevance"""
        try:
            if not url or 'civitai.com' not in url:
                return None
            
            # Extract model information from URL
            model_pattern = r'civitai\.com/models/(\d+)(?:/([^/?]+))?'
            match = re.search(model_pattern, url)
            
            if not match:
                return None
                
            model_id = match.group(1)
            url_model_name = match.group(2) if match.group(2) else ""
            
            # Check for version ID
            version_id = None
            version_match = re.search(r'modelVersionId=(\d+)', url)
            if version_match:
                version_id = version_match.group(1)
            
            # Calculate relevance score
            relevance_score = self._calculate_civitai_relevance_score(model_id, url_model_name, model_name)
            
            return {
                "source": "civitai",
                "model_id": model_id,
                "version_id": version_id,
                "url": url,
                "relevance_score": relevance_score,
                "search_method": "google_api"
            }
            
        except Exception as e:
            print(f"Error parsing CivitAI URL: {e}")
            return None

    def _calculate_civitai_relevance_score(self, model_id: str, url_model_name: str, model_name: str) -> float:
        """Calculate relevance score for CivitAI results"""
        score = 0.0
        model_name_lower = model_name.lower()
        
        # URL model name match
        if url_model_name:
            url_name_clean = url_model_name.replace('-', ' ').replace('_', ' ').lower()
            model_name_clean = model_name_lower.replace('-', ' ').replace('_', ' ')
            
            if model_name_clean == url_name_clean:
                score += 40.0
            elif model_name_lower == url_model_name.lower():
                score += 35.0
            elif model_name_lower in url_model_name.lower():
                score += 15.0
        
        # Base score for valid model ID
        score += 5.0
        
        return score

    async def download_from_global_models(self, global_result: Dict, target_directory: str, session_id: str = None, node_type: str = None, field_name: str = None) -> Dict:
        """Download model from global storage with proper path handling"""
        try:
            model_path = global_result['global_model_path']
            
            MissingModelProgressTracker.update_progress(
                session_id, 
                f"Downloading from global storage: {model_path}...", 
                30
            )
            
            # Determine the correct target directory based on node type
            if node_type:
                actual_target_directory = self.determine_target_directory(
                    global_result['filename'], 
                    node_type, 
                    field_name
                )
            else:
                actual_target_directory = target_directory
            
            print(f"📁 Target directory determined: {actual_target_directory}")
            
            # Get S3 path to understand the source structure
            s3_path = global_result.get('s3_path', '')
            s3_relative_path = None
            if s3_path and 'pod_sessions/global_shared/models/' in s3_path:
                s3_relative_path = s3_path.split('pod_sessions/global_shared/models/')[-1]
                print(f"� S3 relative path: {s3_relative_path}")
            
            # Start the download using global models manager
            download_task = asyncio.create_task(
                self.global_models_manager.download_model(model_path)
            )
            
            # Monitor progress from global models progress store
            while not download_task.done():
                await asyncio.sleep(0.5)
                
                # Check for cancellation
                if session_id and download_cancellation_flags.get(session_id):
                    await self.global_models_manager.cancel_download(model_path)
                    download_task.cancel()
                    MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user", "was_cancelled": True}
                
                # Update progress from global models store
                if model_path in global_progress_store:
                    global_progress = global_progress_store[model_path]
                    progress_percent = global_progress.get('progress', 0)
                    message = global_progress.get('message', 'Downloading from global storage...')
                    
                    # Map global progress (0-100%) to missing models progress (30-90%)
                    mapped_percent = 30 + int(progress_percent * 0.6)
                    MissingModelProgressTracker.update_progress(session_id, message, mapped_percent)
                    
                    # Check if download completed or failed
                    status = global_progress.get('status', 'downloading')
                    if status == 'downloaded':
                        break
                    elif status in ['failed', 'cancelled']:
                        break
            
            # Get final result
            try:
                success = await download_task
            except asyncio.CancelledError:
                return {"success": False, "error": "Download cancelled", "was_cancelled": True}
            
            if success:
                # Determine where the file was actually downloaded by S3
                if s3_relative_path:
                    s3_local_path = self.global_models_manager.models_dir / s3_relative_path
                    s3_directory = f"models/{os.path.dirname(s3_relative_path)}" if os.path.dirname(s3_relative_path) else "models"
                else:
                    s3_local_path = self.global_models_manager.models_dir / model_path
                    s3_directory = f"models/{os.path.dirname(model_path)}" if os.path.dirname(model_path) else "models"
                
                # Check if S3 directory matches our target directory
                s3_directory_clean = s3_directory.rstrip('/')
                actual_target_clean = actual_target_directory.rstrip('/')
                
                final_path = s3_local_path
                
                if s3_directory_clean != actual_target_clean:
                    # S3 path differs from target path, create symlink
                    print(f"🔗 S3 directory ({s3_directory_clean}) differs from target ({actual_target_clean}), creating symlink...")
                    
                    # Create target directory if it doesn't exist
                    target_dir_path = Path(self.comfyui_base) / actual_target_directory
                    target_dir_path.mkdir(parents=True, exist_ok=True)
                    
                    # Create symlink path
                    symlink_path = target_dir_path / global_result['filename']
                    
                    try:
                        # Remove existing symlink if it exists
                        if symlink_path.is_symlink():
                            symlink_path.unlink()
                        elif symlink_path.exists():
                            print(f"⚠️ Target file exists but is not a symlink: {symlink_path}")
                        
                        # Create symlink
                        symlink_path.symlink_to(s3_local_path)
                        print(f"✅ Created symlink: {symlink_path} -> {s3_local_path}")
                        final_path = symlink_path
                        
                        # Register the symlinked model in local models_config.json
                        if MODEL_CONFIG_AVAILABLE and model_config_manager:
                            try:
                                model_type = self._determine_model_type_from_path(actual_target_directory)
                                registration_success = model_config_manager.register_s3_model(
                                    local_path=str(symlink_path),
                                    s3_path=s3_path,
                                    model_name=global_result['filename'],
                                    model_type=model_type,
                                    sym_linked_from=str(s3_local_path)
                                )
                                if registration_success:
                                    print(f"✅ Registered symlinked model in config: {symlink_path}")
                                else:
                                    print(f"⚠️ Failed to register symlinked model in config: {symlink_path}")
                            except Exception as reg_error:
                                print(f"⚠️ Error registering symlinked model: {reg_error}")
                        
                    except Exception as symlink_error:
                        print(f"⚠️ Failed to create symlink: {symlink_error}")
                        print(f"📁 Model available at S3 location: {s3_local_path}")
                        final_path = s3_local_path
                
                MissingModelProgressTracker.set_completed(
                    session_id,
                    f"Successfully downloaded {global_result['filename']} from global storage"
                )
                
                return {
                    "success": True,
                    "source": "global_models",
                    "message": f"Downloaded {global_result['filename']} from global storage",
                    "path": str(final_path),
                    "directory": actual_target_directory,
                    "original_name": global_result['filename'],
                    "search_method": "global_storage",
                    "symlink_created": s3_directory_clean != actual_target_clean
                }
            else:
                # Check if it was cancelled
                if model_path in global_progress_store:
                    global_status = global_progress_store[model_path].get('status', 'failed')
                    if global_status == 'cancelled':
                        return {"success": False, "error": "Download cancelled by user", "was_cancelled": True}
                
                error_msg = "Failed to download from global storage"
                if model_path in global_progress_store:
                    error_msg = global_progress_store[model_path].get('message', error_msg)
                
                print(f"❌ Global model download failed: {error_msg}")
                return {"success": False, "error": f"Global storage download failed: {error_msg}"}
                
        except Exception as e:
            error_msg = f"Error downloading from global storage: {str(e)}"
            print(f"❌ {error_msg}")
            return {"success": False, "error": error_msg}

    async def search_global_models(self, model_name: str, session_id: str = None) -> Optional[Dict]:
        """Search for model in global storage first"""
        if not self.global_models_manager or not GLOBAL_MODELS_AVAILABLE:
            print("⚠️ Global models not available, skipping global search")
            return None
            
        try:
            MissingModelProgressTracker.update_progress(session_id, f"Searching global models for '{model_name}'...", 15)
            
            # Get global models structure
            global_structure = await self.global_models_manager.get_global_models_structure()
            if not global_structure:
                print("❌ No global models structure available")
                return None
            
            print(f"🔍 Searching global models for: {model_name}")
            
            # Search for exact filename matches in all categories
            best_match = None
            best_score = 0
            
            for category, category_data in global_structure.items():
                if not isinstance(category_data, dict):
                    continue
                    
                for filename, file_info in category_data.items():
                    if not isinstance(file_info, dict) or file_info.get('type') != 'file':
                        continue
                    
                    # Calculate match score
                    score = self._calculate_global_model_match_score(filename, model_name)
                    
                    if score > best_score and score >= 50:  # Only consider good matches
                        best_score = score
                        best_match = {
                            "source": "global_models",
                            "category": category,
                            "filename": filename,
                            "global_model_path": f"{category}/{filename}",
                            "s3_path": file_info.get('s3_path'),  # Include S3 path for destination determination
                            "size": file_info.get('size', 0),
                            "relevance_score": score,
                            "search_method": "global_storage"
                        }
                        
                        print(f"🎯 Found global model match: {category}/{filename} (score: {score}) with S3 path: {file_info.get('s3_path', 'N/A')}")
            
            if best_match:
                print(f"✅ Best global model match: {best_match['global_model_path']} (score: {best_score})")
                return best_match
            else:
                print(f"❌ No matching models found in global storage for '{model_name}'")
                return None
                
        except Exception as e:
            print(f"Error searching global models: {e}")
            return None

    def _calculate_global_model_match_score(self, filename: str, model_name: str) -> float:
        """Calculate relevance score for global model matches"""
        score = 0.0
        model_name_lower = model_name.lower().strip()
        filename_lower = filename.lower().strip()
        
        # Remove common extensions for comparison
        model_name_base = model_name_lower
        filename_base = filename_lower
        
        for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']:
            if model_name_base.endswith(ext):
                model_name_base = model_name_base[:-len(ext)]
            if filename_base.endswith(ext):
                filename_base = filename_base[:-len(ext)]
        
        # Exact match (highest priority)
        if model_name_lower == filename_lower:
            score += 100.0
        elif model_name_base == filename_base:
            score += 95.0
        elif model_name_lower == filename_base:
            score += 90.0
        elif model_name_base == filename_lower:
            score += 85.0
        
        # Partial matches
        elif model_name_base in filename_base:
            score += 70.0
        elif filename_base in model_name_base:
            score += 65.0
        elif model_name_lower in filename_lower:
            score += 60.0
        elif filename_lower in model_name_lower:
            score += 55.0
        
        # Fuzzy matching for slight variations
        else:
            # Check for common variations (underscores, hyphens, spaces)
            normalized_model = model_name_base.replace('_', '').replace('-', '').replace(' ', '')
            normalized_filename = filename_base.replace('_', '').replace('-', '').replace(' ', '')
            
            if normalized_model == normalized_filename:
                score += 80.0
            elif normalized_model in normalized_filename:
                score += 50.0
            elif normalized_filename in normalized_model:
                score += 45.0
        
        return score

    async def download_missing_model(self, model_name: str, node_type: str = None, session_id: str = None, field_name: str = None) -> Dict:
        """Download a missing model by first checking global storage, then searching HF and CivitAI"""
        try:
            # Check for cancellation at the very start
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            MissingModelProgressTracker.update_progress(session_id, f"Processing model: {model_name}...", 5)
            print(f"🔍 Starting download for model: {model_name} (type: {node_type})")
            
            # If node_type is not provided, try to extract it from workflow
            if not node_type:
                node_type = self.get_node_type_from_workflow(model_name)
                if node_type:
                    print(f"📋 Extracted node type from workflow: {node_type}")
            
            # Determine target directory using the utility function
            target_directory = self.determine_target_directory(model_name, node_type, field_name)
            print(f"📁 Target directory determined: {target_directory}")
            
            # Check for cancellation before proceeding
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            MissingModelProgressTracker.update_progress(session_id, f"Searching for: {model_name}", 10)
            
            # 🆕 STEP 1: Check global models first
            global_result = await self.search_global_models(model_name, session_id)
            global_download_attempted = False
            global_download_success = False

            print(f"🔍 Global search result: {global_result}")
            
            # Check for cancellation after search
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            if global_result:
                print(f"✅ Found model in global storage: {global_result['global_model_path']}")
                
                # Try downloading from global storage with node type and field name
                global_download_attempted = True
                global_download_result = await self.download_from_global_models(
                    global_result, 
                    target_directory, 
                    session_id, 
                    node_type, 
                    field_name
                )
                
                # Check if global download was cancelled by user
                if global_download_result.get("was_cancelled", False):
                    print(f"🚫 Global storage download cancelled by user, stopping download process...")
                    MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                
                # If global download succeeded, return immediately
                if global_download_result["success"]:
                    global_download_success = True
                    return global_download_result
                
                # Global download failed for other reasons, continue to internet search
                print(f"⚠️ Global storage download failed: {global_download_result.get('error')}")
                MissingModelProgressTracker.update_progress(
                    session_id, 
                    f"Global storage failed, searching internet: {global_download_result.get('error', 'Unknown error')}", 
                    20
                )
            else:
                print(f"❌ Model not found in global storage, searching internet...")
                MissingModelProgressTracker.update_progress(session_id, "Not found in global storage, searching internet...", 20)
 
            # STEP 2: Proceed with internet search (only if global storage failed or model not found)
            # Check for cancellation again before proceeding to internet search
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            # Track if we tried Hugging Face and what happened
            hf_attempted = False
            hf_error = None
            hf_was_cancelled = False
            
            # Search Hugging Face first (with DuckDuckGo fallback built-in)
            MissingModelProgressTracker.update_progress(session_id, "Searching Hugging Face...", 25)
            
            # Check for cancellation before HF search
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
                
            hf_result = await self.search_huggingface_with_google(model_name, session_id)
            
            # Check for cancellation after HF search
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            if hf_result and not (session_id and download_cancellation_flags.get(session_id)):
                MissingModelProgressTracker.update_progress(session_id, f"Found on Hugging Face: {hf_result['repo_id']}", 40)
                hf_attempted = True
                
                try:
                    # Use the exact URL found by search
                    hf_url = hf_result["url"]
                    
                    # Create a progress callback that updates missing models progress
                    def hf_progress_callback(sess_id, message, percentage):
                        # Check for cancellation in callback
                        if sess_id and download_cancellation_flags.get(sess_id):
                            return  # Don't update progress if cancelled
                        # Map HF progress (75-95%) to missing models progress (60-90%)
                        if percentage >= 75:
                            mapped_percentage = 60 + int((percentage - 75) / 20 * 30)  # 75-95% maps to 60-90%
                        else:
                            mapped_percentage = percentage
                        MissingModelProgressTracker.update_progress(sess_id, message, mapped_percentage)
                    
                    result = await self.hf_api.download_from_huggingface(
                        hf_url=hf_url,
                        target_fsm_path=target_directory,
                        overwrite=False,
                        session_id=session_id,
                        progress_callback=hf_progress_callback
                    )
                    
                    # Check for cancellation after download attempt
                    if session_id and download_cancellation_flags.get(session_id):
                        MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                        return {"success": False, "error": "Download cancelled by user"}
                    
                    if result["success"]:
                        search_method = hf_result.get('search_method', 'unknown')
                        MissingModelProgressTracker.set_completed(
                            session_id, 
                            f"Successfully downloaded {model_name} from Hugging Face (via {search_method})"
                        )
                        return {
                            "success": True,
                            "source": "huggingface",
                            "message": f"Downloaded {model_name} from Hugging Face",
                            "path": result.get("path"),
                            "directory": target_directory,
                            "original_name": model_name,
                            "search_method": search_method
                        }
                    else:
                        hf_error = result.get('error', 'Unknown error')
                        # Check if the error was due to user cancellation
                        if "cancelled" in hf_error.lower() or "canceled" in hf_error.lower():
                            hf_was_cancelled = True
                            print(f"HF download was cancelled by user: {hf_error}")
                        else:
                            print(f"HF download failed: {hf_error}")
                        
                except Exception as hf_error_exception:
                    hf_error = str(hf_error_exception)
                    # Check if the exception was due to user cancellation
                    if "cancelled" in hf_error.lower() or "canceled" in hf_error.lower():
                        hf_was_cancelled = True
                        print(f"Hugging Face download was cancelled by user: {hf_error}")
                    else:
                        print(f"Hugging Face download error: {hf_error}")
            else:
                print(f"❌ No Hugging Face results found for '{model_name}'")
            
            # Try CivitAI if HF failed but wasn't cancelled by user
            should_try_civitai = (
                (hf_attempted and hf_error and not hf_was_cancelled) or
                (not hf_attempted)  # No HF result found
            )
            
            # Always check for cancellation before proceeding to CivitAI
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            
            if should_try_civitai and not (session_id and download_cancellation_flags.get(session_id)):
                if hf_attempted and hf_was_cancelled:
                    # If HF was cancelled, don't try CivitAI
                    MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                elif hf_attempted:
                    MissingModelProgressTracker.update_progress(session_id, f"Hugging Face failed ({hf_error}), trying CivitAI...", 45)
                else:
                    MissingModelProgressTracker.update_progress(session_id, "Hugging Face not found, searching CivitAI...", 45)
                
                # Check for cancellation before CivitAI search
                if session_id and download_cancellation_flags.get(session_id):
                    MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                
                civitai_result = await self.search_civitai_with_google(model_name, session_id)
                
                # Check for cancellation after CivitAI search
                if session_id and download_cancellation_flags.get(session_id):
                    MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                    return {"success": False, "error": "Download cancelled by user"}
                
                if civitai_result and not (session_id and download_cancellation_flags.get(session_id)):
                    MissingModelProgressTracker.update_progress(session_id, f"Found on CivitAI: {civitai_result['model_id']}", 60)
                    
                    try:
                        # Use the found URL from search
                        civitai_url = civitai_result["url"]
                        
                        # Create a progress callback that updates missing models progress
                        def civitai_progress_callback(sess_id, message, percentage):
                            # Check for cancellation in callback
                            if sess_id and download_cancellation_flags.get(sess_id):
                                return  # Don't update progress if cancelled
                            # Map CivitAI progress (75-95%) to missing models progress (70-90%)
                            if percentage >= 75:
                                mapped_percentage = 70 + int((percentage - 75) / 20 * 20)  # 75-95% maps to 70-90%
                            else:
                                mapped_percentage = percentage
                            MissingModelProgressTracker.update_progress(sess_id, message, mapped_percentage)
                        
                        result = await self.civitai_api.download_from_civitai(
                            civitai_url=civitai_url,
                            target_fsm_path=target_directory,
                            filename=model_name,  # Use original name with extension
                            overwrite=False,
                            session_id=session_id,
                            progress_callback=civitai_progress_callback
                        )
                        
                        # Check for cancellation after download attempt
                        if session_id and download_cancellation_flags.get(session_id):
                            MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                            return {"success": False, "error": "Download cancelled by user"}
                        
                        if result["success"]:
                            search_method = civitai_result.get('search_method', 'unknown')
                            MissingModelProgressTracker.set_completed(
                                session_id,
                                f"Successfully downloaded {model_name} from CivitAI (via {search_method})"
                            )
                            return {
                                "success": True,
                                "source": "civitai",
                                "message": f"Downloaded {model_name} from CivitAI",
                                "path": result.get("path"),
                                "directory": target_directory,
                                "original_name": model_name,
                                "search_method": search_method
                            }
                        else:
                            print(f"CivitAI download failed: {result.get('error')}")
                            
                    except Exception as civitai_error:
                        print(f"CivitAI download error: {civitai_error}")
                else:
                    print(f"❌ No CivitAI results found for '{model_name}'")
            
            # If we get here, all sources failed or were not found
            if session_id and download_cancellation_flags.get(session_id):
                MissingModelProgressTracker.set_cancelled(session_id, "Download cancelled by user")
                return {"success": False, "error": "Download cancelled by user"}
            else:
                # Create detailed error message including global storage attempt
                error_parts = []
                if global_download_attempted:
                    error_parts.append("Global storage: Download failed")
                else:
                    error_parts.append("Global storage: Not found")
                    
                if hf_attempted:
                    if hf_was_cancelled:
                        error_parts.append("Hugging Face: Cancelled by user")
                    else:
                        error_parts.append(f"Hugging Face: {hf_error}")
                else:
                    error_parts.append("Hugging Face: No results found")
                
                if should_try_civitai:
                    error_parts.append("CivitAI: No results found or download failed")
                else:
                    error_parts.append("CivitAI: Not attempted due to cancellation")
                
                full_error = f"Model '{model_name}' not found. " + "; ".join(error_parts)
                
                MissingModelProgressTracker.set_error(session_id, full_error)
                return {
                    "success": False,
                    "error": full_error,
                    "show_community_cta": True
                }
                
        except Exception as e:
            error_msg = f"Error downloading missing model: {str(e)}"
            MissingModelProgressTracker.set_error(session_id, error_msg)
            return {
                "success": False,
                "error": error_msg,
                "show_community_cta": True
            }
        finally:
            # Clean up cancellation flag
            if session_id and session_id in download_cancellation_flags:
                del download_cancellation_flags[session_id]

    async def get_community_link(self, model_name: str, error_logs: str = "", runpod_id: str = None) -> str:
        """Get community support link for failed downloads"""
        try:
            # Prepare the request data
            request_data = {
                "model_name": model_name,
                "error_logs": error_logs,
                "runpod_id": runpod_id or os.environ.get("RUNPOD_POD_ID", "unknown")
            }
            
            # Mock community API - replace with actual endpoint
            community_base_url = os.environ.get("COMMUNITY_API_URL", "https://your-community-api.com")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{community_base_url}/get_community_link",
                    json=request_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("community_link", self._generate_fallback_community_link(model_name))
                    else:
                        return self._generate_fallback_community_link(model_name)
                        
        except Exception as e:
            print(f"Error getting community link: {e}")
            return self._generate_fallback_community_link(model_name)

    def _generate_fallback_community_link(self, model_name: str) -> str:
        """Generate a fallback community link"""
        base_discord_url = "https://discord.gg/your-server"
        message = f"I need help downloading the model: {model_name}"
        
        import urllib.parse
        encoded_message = urllib.parse.quote(message)
        
        return f"{base_discord_url}?message={encoded_message}"

    def get_node_type_from_workflow(self, model_name: str) -> Optional[str]:
        """Extract node type from current workflow JSON + model file name"""
        try:
            # Try to get the current workflow from ComfyUI API
            workflow_data = None
            
            # First, check if we can access the workflow from the global state
            try:
                import execution
                if hasattr(execution, 'current_workflow') and execution.current_workflow:
                    workflow_data = execution.current_workflow
            except ImportError:
                pass
            
            if not workflow_data:
                # Try to read from the UI state if available
                try:
                    from server import PromptServer
                    if hasattr(PromptServer, 'instance') and PromptServer.instance:
                        # This is a fallback approach - in practice, you might need to
                        # implement a way to access the current workflow
                        pass
                except ImportError:
                    pass
            
            if workflow_data:
                # Search through workflow nodes to find which node is using this model
                for node_id, node_data in workflow_data.items():
                    if isinstance(node_data, dict) and 'class_type' in node_data:
                        class_type = node_data['class_type']
                        inputs = node_data.get('inputs', {})
                        
                        # Check if any input value matches our model name
                        for input_key, input_value in inputs.items():
                            if isinstance(input_value, str) and input_value == model_name:
                                print(f"🎯 Found model '{model_name}' in node '{class_type}' input '{input_key}'")
                                return class_type
                        
                        # Also check for partial matches (model name without extension)
                        model_base = model_name.rsplit('.', 1)[0] if '.' in model_name else model_name
                        for input_key, input_value in inputs.items():
                            if isinstance(input_value, str):
                                input_base = input_value.rsplit('.', 1)[0] if '.' in input_value else input_value
                                if input_base == model_base:
                                    print(f"🎯 Found model '{model_name}' (partial) in node '{class_type}' input '{input_key}'")
                                    return class_type
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error extracting node type from workflow: {e}")
            return None

    def determine_target_directory(self, model_name: str, node_type: str = None, field_name: str = None) -> str:
        """Determine target directory based on node type using the utility function"""
        try:
            # If node_type is provided, use the utility function
            if node_type:
                directories = get_directories_for_loader_class(node_type)
                if directories:
                    # Handle special case for VAE nodes
                    if node_type == "VAELoader" and len(directories) > 1:
                        # Check field_name to determine vae vs vae_approx
                        if field_name and 'approx' in field_name.lower():
                            return "models/vae_approx"
                        else:
                            return "models/vae"
                    else:
                        # Use the first directory for other nodes
                        return f"models/{directories[0]}"
            
            # Fallback to the original inference method
            return self.infer_model_directory(model_name, node_type)
            
        except Exception as e:
            print(f"⚠️ Error determining target directory: {e}")
            return self.infer_model_directory(model_name, node_type)

# Global instance
missing_model_handler = MissingModelHandler()
