import os
import asyncio
import json
from pathlib import Path
from typing import Optional, Dict
from playwright.async_api import async_playwright, BrowserContext, Page
import folder_paths
from fake_useragent import UserAgent

ua = UserAgent(platforms=['Windows', 'Mac', 'Linux'], min_version="120.0")


class SharedBrowserSessionManager:
    """
    Shared browser session manager for ComfyUI File System Manager.
    Maintains persistent browser sessions with authentication data for
    Google Drive and Hugging Face.
    """
    
    _instance: Optional['SharedBrowserSessionManager'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.comfyui_base = Path(folder_paths.base_path)
        self.session_dir = self.comfyui_base / ".browser-session"
        self.session_dir.mkdir(exist_ok=True)
        
        # Browser instances
        self._playwright = None
        self._browser = None
        self._contexts: Dict[str, BrowserContext] = {}
        
        # Session data paths
        self.google_session_path = self.session_dir / "google_drive"
        self.huggingface_session_path = self.session_dir / "huggingface"
        
        # Create session directories
        self.google_session_path.mkdir(exist_ok=True)
        self.huggingface_session_path.mkdir(exist_ok=True)
        
        session_info = f"Session data: {self.session_dir}"
        print(f"🔧 Browser session manager initialized. {session_info}")

    async def _ensure_browser(self):
        """Ensure browser is running"""
        if self._playwright is None or self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            print("🌐 Browser launched for shared session management")

    async def get_context(self, service: str,
                          **context_options) -> BrowserContext:
        """
        Get or create a persistent browser context for a service.
        
        Args:
            service: 'google_drive' or 'huggingface'
            **context_options: Additional context options
        """
        async with self._lock:
            await self._ensure_browser()
            
            if service in self._contexts:
                # Check if context is still valid
                try:
                    # Test context by getting pages
                    await self._contexts[service].pages
                    return self._contexts[service]
                except Exception:
                    # Context is dead, remove it
                    del self._contexts[service]
            
            # Create new context with persistent storage
            if service == 'google_drive':
                session_path = self.google_session_path
            else:
                session_path = self.huggingface_session_path
            
            user_agent = service == ua.random if service == 'google_drive' else ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36')
            
            session_state_file = session_path / 'session_state.json'
            storage_state = (str(session_state_file)
                             if session_state_file.exists() else None)
            
            default_options = {
                'user_agent': user_agent,
                'viewport': {'width': 1920, 'height': 1080},
                'storage_state': storage_state,
                'accept_downloads': True,
                'java_script_enabled': True,
            }
            
            # Merge with user options
            default_options.update(context_options)
            
            try:
                context = await self._browser.new_context(**default_options)
                self._contexts[service] = context
                
                print(f"🔐 Created persistent browser context for {service}")
                return context
                
            except Exception as e:
                msg = f"Failed to load session state for {service}, creating fresh context: {e}"
                print(f"⚠️ {msg}")
                # Try without storage state
                if 'storage_state' in default_options:
                    del default_options['storage_state']
                context = await self._browser.new_context(**default_options)
                self._contexts[service] = context
                return context

    async def save_session_state(self, service: str):
        """Save the current session state for a service"""
        if service not in self._contexts:
            return
        
        try:
            if service == 'google_drive':
                session_path = self.google_session_path
            else:
                session_path = self.huggingface_session_path
            
            state_file = session_path / 'session_state.json'
            
            # Save browser state (cookies, localStorage, etc.)
            storage_state = await self._contexts[service].storage_state()
            
            with open(state_file, 'w') as f:
                json.dump(storage_state, f, indent=2)
            
            print(f"💾 Saved session state for {service}")
            
        except Exception as e:
            print(f"⚠️ Failed to save session state for {service}: {e}")

    async def create_page(self, service: str, **page_options) -> Page:
        """Create a new page in the service context"""
        context = await self.get_context(service)
        page = await context.new_page()
        
        # Set additional page options if provided
        if 'extra_http_headers' in page_options:
            await page.set_extra_http_headers(page_options['extra_http_headers'])
        
        return page

    async def is_authenticated(self, service: str) -> bool:
        """Check if the service is already authenticated"""
        try:
            context = await self.get_context(service)
            page = await context.new_page()
            
            if service == 'google_drive':
                # Check Google authentication
                await page.goto('https://drive.google.com/', timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Look for signs of being logged in
                login_indicators = [
                    '[data-tooltip="Google Account"]',
                    '[aria-label*="Google Account"]',
                    '.gb_d',  # Google account avatar
                    '[href*="accounts.google.com/SignOutOptions"]'
                ]
                
                for indicator in login_indicators:
                    if await page.locator(indicator).count() > 0:
                        await page.close()
                        print(f"✅ {service} is already authenticated")
                        return True
                
            elif service == 'huggingface':
                # Check Hugging Face authentication
                await page.goto('https://huggingface.co/', timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Look for signs of being logged in
                login_indicators = [
                    'a[href*="/settings"]',
                    'button:has-text("Log out")',
                    '[data-testid="user-menu"]',
                    '.avatar',
                    '[aria-label*="user"]'
                ]
                
                for indicator in login_indicators:
                    if await page.locator(indicator).count() > 0:
                        await page.close()
                        print(f"✅ {service} is already authenticated")
                        return True
            
            await page.close()
            print(f"❌ {service} is not authenticated")
            return False
            
        except Exception as e:
            print(f"⚠️ Error checking authentication for {service}: {e}")
            return False

    async def login_google_drive(self, email: str = None, 
                                 password: str = None) -> bool:
        """Login to Google Drive"""
        try:
            # Use environment variables if not provided
            email = email or os.environ.get("GOOGLE_EMAIL")
            password = password or os.environ.get("GOOGLE_PASSWORD")
            
            if not email or not password:
                print("❌ GOOGLE_EMAIL or GOOGLE_PASSWORD not provided")
                return False
            
            page = await self.create_page('google_drive')
            
            # Navigate to Google login
            await page.goto('https://accounts.google.com/signin', 
                           timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Enter email
            await page.fill('input[type="email"]', email)
            await page.click('#identifierNext')
            await page.wait_for_timeout(3000)
            
            # Enter password
            await page.fill('input[type="password"]', password)
            await page.click('#passwordNext')
            await page.wait_for_timeout(5000)
            
            # Check if login was successful
            is_authenticated = await self.is_authenticated('google_drive')
            
            if is_authenticated:
                await self.save_session_state('google_drive')
                print("✅ Google Drive login successful")
                
            await page.close()
            return is_authenticated
            
        except Exception as e:
            print(f"❌ Google Drive login failed: {e}")
            return False

    async def login_huggingface(self, username: str = None, 
                                password: str = None) -> bool:
        """Login to Hugging Face"""
        try:
            # Use environment variables if not provided
            username = username or os.environ.get("HF_USERNAME")
            password = password or os.environ.get("HF_PASSWORD")
            
            if not username or not password:
                print("❌ HF_USERNAME or HF_PASSWORD not provided")
                return False
            
            page = await self.create_page('huggingface')
            
            # Navigate to Hugging Face login
            await page.goto('https://huggingface.co/login', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Fill login form
            username_selectors = ('input[name="username"], '
                                'input[placeholder*="Username"], '
                                'input[placeholder*="Email"]')
            await page.fill(username_selectors, username)
            await page.fill('input[name="password"], input[type="password"]', 
                          password)
            
            # Submit form
            submit_selectors = ('button[type="submit"], input[type="submit"], '
                              'button:has-text("Login")')
            await page.click(submit_selectors)
            await page.wait_for_timeout(5000)
            
            # Check if login was successful
            is_authenticated = await self.is_authenticated('huggingface')
            
            if is_authenticated:
                await self.save_session_state('huggingface')
                print("✅ Hugging Face login successful")
                
            await page.close()
            return is_authenticated
            
        except Exception as e:
            print(f"❌ Hugging Face login failed: {e}")
            return False

    async def ensure_authenticated(self, service: str, 
                                   force_login: bool = False) -> bool:
        """Ensure a service is authenticated, login if necessary"""
        if not force_login and await self.is_authenticated(service):
            return True
        
        if service == 'google_drive':
            # No Authentication required for Google Drive
            #return await self.login_google_drive()
            return True
        elif service == 'huggingface':
            return await self.login_huggingface()
        else:
            print(f"❌ Unknown service: {service}")
            return False

    async def cleanup_context(self, service: str):
        """Clean up a specific context"""
        if service in self._contexts:
            try:
                await self.save_session_state(service)
                await self._contexts[service].close()
                del self._contexts[service]
                print(f"🧹 Cleaned up context for {service}")
            except Exception as e:
                print(f"⚠️ Error cleaning up context for {service}: {e}")

    async def cleanup_all(self):
        """Clean up all browser resources"""
        async with self._lock:
            # Save all session states
            for service in list(self._contexts.keys()):
                await self.cleanup_context(service)
            
            # Close browser
            if self._browser:
                try:
                    await self._browser.close()
                    self._browser = None
                    print("🧹 Browser closed")
                except Exception as e:
                    print(f"⚠️ Error closing browser: {e}")
            
            # Stop playwright
            if self._playwright:
                try:
                    await self._playwright.stop()
                    self._playwright = None
                    print("🧹 Playwright stopped")
                except Exception as e:
                    print(f"⚠️ Error stopping playwright: {e}")

    def __del__(self):
        """Cleanup when instance is destroyed"""
        if hasattr(self, '_browser') and self._browser:
            try:
                # Try to schedule cleanup if event loop is running
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.cleanup_all())
            except Exception:
                pass
