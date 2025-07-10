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
            
            default_options = {
                'user_agent': user_agent,
                'viewport': {'width': 1920, 'height': 1080},
                'accept_downloads': True,
                'java_script_enabled': True,
            }
            
           
        try:
            # Merge with user options
            default_options.update(context_options)
            context = await self._browser.new_context(**default_options)
            
            # Try to load cookies from session_state.json
            cookies_file = session_path / 'session_state.json'
            if cookies_file.exists():
                with open(cookies_file, 'r') as f:
                    cookie_data = json.load(f)
                
                if cookie_data.get('cookies'):
                    print(f"🍪 Loading {len(cookie_data['cookies'])} cookies from session_state.json")
                    await context.add_cookies(cookie_data['cookies'])
                    print(f"✅ Successfully loaded cookies into {service} context")
            
            self._contexts[service] = context
            return context
            
        except Exception as fallback_error:
            print(f"❌ Cookie fallback also failed for {service}: {fallback_error}")
            # Create completely fresh context as last resort
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
            
            # Also get fresh cookies directly from context
            fresh_cookies = await self._contexts[service].cookies()
            
            # Merge fresh cookies into storage state to ensure we have all cookies
            if fresh_cookies:
                storage_state['cookies'] = fresh_cookies
                print(f"🍪 Updated storage state with {len(fresh_cookies)} fresh cookies")
            
            # Debug: Print cookie information for troubleshooting
            if storage_state.get('cookies'):
                cookie_count = len(storage_state['cookies'])
                print(f"🍪 Found {cookie_count} cookies for {service}")
                for cookie in storage_state['cookies']:
                    name = cookie.get('name')
                    domain = cookie.get('domain')
                    secure = cookie.get('secure', False)
                    print(f"  - {name}: {domain} (secure: {secure})")
                    
                # Save the updated session state
                with open(state_file, 'w') as f:
                    json.dump(storage_state, f, indent=2)
                
                # Also save just the cookies to a separate file for easy inspection
                cookies_file = session_path / 'session_state.json'
                cookie_data = {
                    'service': service,
                    'timestamp': str(asyncio.get_event_loop().time()),
                    'cookies': fresh_cookies,
                    'total_cookies': len(fresh_cookies)
                }
                with open(cookies_file, 'w') as f:
                    json.dump(cookie_data, f, indent=2)
                
                print(f"💾 Saved {len(fresh_cookies)} cookies to session_state.json")
            else:
                print(f"⚠️ No cookies found in session state for {service}")
                # Still save the session state even without cookies
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
                # Check Hugging Face authentication - more thorough check
                await page.goto('https://huggingface.co/', timeout=30000)
                await page.wait_for_timeout(3000)
                
                # First check for user menu/profile indicators
                login_indicators = [
                    'a[href*="/settings"]',
                    'button:has-text("Log out")',
                    '[data-testid="user-menu"]',
                    '.avatar',
                    '[aria-label*="user"]',
                    'a[href*="/profile"]',
                    '.user-menu'
                ]
                
                for indicator in login_indicators:
                    if await page.locator(indicator).count() > 0:
                        await page.close()
                        print(f"✅ {service} is already authenticated")
                        return True
                
                # Secondary check: try accessing a protected page
                try:
                    await page.goto('https://huggingface.co/settings/profile', 
                                  timeout=10000)
                    await page.wait_for_timeout(2000)
                    
                    # If we can access settings, we're logged in
                    current_url = page.url
                    if 'settings' in current_url and 'login' not in current_url:
                        await page.close()
                        print(f"✅ {service} authenticated (via settings access)")
                        return True
                        
                except Exception:
                    # If settings access fails, we're likely not logged in
                    pass
                
                # Final check: look for login/register buttons (indicates not logged in)
                login_buttons = await page.locator(
                    'a[href*="/login"], button:has-text("Sign in"), '
                    'button:has-text("Log in"), a:has-text("Sign up")'
                ).count()
                
                if login_buttons > 0:
                    await page.close()
                    print(f"❌ {service} is not authenticated (login buttons found)")
                    return False
            
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
            
            # Wait for navigation after login
            await page.wait_for_timeout(5000)
            
            # Check if we're still on login page (indicates failure)
            current_url = page.url
            if 'login' in current_url.lower():
                print("❌ Still on login page, checking for errors...")
                # Look for error messages
                error_selectors = [
                    '.error', '.alert-error', '[class*="error"]',
                    '[class*="invalid"]', '.text-red-500'
                ]
                for selector in error_selectors:
                    if await page.locator(selector).count() > 0:
                        error_text = await page.locator(selector).text_content()
                        print(f"❌ Login error: {error_text}")
                        await page.close()
                        return False
            
            # Force wait for cookies to be set
            await page.wait_for_timeout(3000)
            
            # Save cookies immediately after login attempt
            print("🔄 Capturing cookies immediately after login...")
            await self._capture_and_save_cookies('huggingface')
            
            # Check if login was successful
            is_authenticated = await self.is_authenticated('huggingface')
            
            if is_authenticated:
                # Save session state immediately after successful login
                await self.save_session_state('huggingface')
                print("✅ Hugging Face login successful")
                
                # Also save cookies separately for debugging
                await self._debug_save_cookies('huggingface')
            else:
                print("❌ Login appeared to succeed but authentication check failed")
                await self._debug_save_cookies('huggingface')
                
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

    async def _debug_save_cookies(self, service: str):
        """Debug method to save cookies separately for troubleshooting"""
        try:
            if service not in self._contexts:
                return
            
            # Get all cookies from the context
            cookies = await self._contexts[service].cookies()
            
            # Save to debug file
            if service == 'google_drive':
                session_path = self.google_session_path
            else:
                session_path = self.huggingface_session_path
            
            debug_file = session_path / 'debug_cookies.json'
            
            with open(debug_file, 'w') as f:
                json.dump(cookies, f, indent=2)
            
            print(f"🐛 Debug: Saved {len(cookies)} cookies for {service}")
            
            # Print important cookies for HuggingFace
            if service == 'huggingface':
                important_cookies = [
                    'session', 'token', 'auth', 'user', 'csrf',
                    'huggingface', 'hf_', '_hf'
                ]
                found_important = []
                for cookie in cookies:
                    cookie_name = cookie.get('name', '').lower()
                    for important in important_cookies:
                        if important in cookie_name:
                            found_important.append(cookie.get('name'))
                            break
                
                if found_important:
                    print(f"🔑 Found important cookies: {found_important}")
                else:
                    print("⚠️ No important authentication cookies found")
                    
        except Exception as e:
            print(f"⚠️ Failed to save debug cookies for {service}: {e}")
    
    async def _capture_and_save_cookies(self, service: str):
        """Immediately capture and save cookies after login"""
        try:
            if service not in self._contexts:
                print(f"⚠️ No context found for {service}")
                return
            
            # Get fresh cookies from the context
            fresh_cookies = await self._contexts[service].cookies()
            
            if service == 'google_drive':
                session_path = self.google_session_path
            else:
                session_path = self.huggingface_session_path
            
            # Save cookies to session_state.json immediately
            cookies_file = session_path / 'session_state.json'
            cookie_data = {
                'service': service,
                'timestamp': str(asyncio.get_event_loop().time()),
                'cookies': fresh_cookies,
                'total_cookies': len(fresh_cookies),
                'capture_type': 'immediate_post_login'
            }
            
            with open(cookies_file, 'w') as f:
                json.dump(cookie_data, f, indent=2)
            
            print(f"🚀 Immediately captured {len(fresh_cookies)} cookies for {service}")
            
            # Print important authentication cookies for debugging
            if service == 'huggingface' and fresh_cookies:
                auth_cookies = []
                for cookie in fresh_cookies:
                    name = cookie.get('name', '').lower()
                    if any(key in name for key in ['session', 'token', 'auth', 'csrf', 'hf']):
                        auth_cookies.append(cookie.get('name'))
                
                if auth_cookies:
                    print(f"🔐 Found authentication cookies: {auth_cookies}")
                else:
                    print("⚠️ No obvious authentication cookies detected")
                    
        except Exception as e:
            print(f"❌ Failed to capture cookies for {service}: {e}")

    async def load_existing_cookies(self, service: str):
        """Load existing cookies into the context if available"""
        try:
            if service not in self._contexts:
                return False
            
            if service == 'google_drive':
                session_path = self.google_session_path
            else:
                session_path = self.huggingface_session_path
            
            cookies_file = session_path / 'session_state.json'
            
            if not cookies_file.exists():
                print(f"📄 No session_state.json found for {service}")
                return False
            
            with open(cookies_file, 'r') as f:
                cookie_data = json.load(f)
            
            cookies = cookie_data.get('cookies', [])
            if not cookies:
                print(f"🍪 No cookies found in session_state.json for {service}")
                return False
            
            # Add cookies to the context
            await self._contexts[service].add_cookies(cookies)
            print(f"✅ Loaded {len(cookies)} cookies into {service} context")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load existing cookies for {service}: {e}")
            return False
