from pathlib import Path
from datetime import datetime

class ScreenshotManager:
    def __init__(self):
        # Create screenshots directory with session-based organization
        self.screenshots_base_dir = Path(__file__).parent.parent / "screenshots"
        self.screenshots_base_dir.mkdir(parents=True, exist_ok=True)
        # Session-specific directory will be created when first screenshot is taken
        self.current_session_dir = None

    def get_session_screenshots_dir(self):
        """Get or create the current session's screenshot directory"""
        if self.current_session_dir is None:
            # Create session directory based on current timestamp
            session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_session_dir = self.screenshots_base_dir / f"session_{session_timestamp}/huggingface"
            self.current_session_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created screenshot session directory: {self.current_session_dir}")
        
        return self.current_session_dir

    async def take_screenshot(self, page, filename_prefix: str, description: str = ""):
        """Take a screenshot for debugging/reference purposes"""
        try:
            # Get session directory
            session_dir = self.get_session_screenshots_dir()
            
            # Create filename with detailed timestamp
            timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]  # Include milliseconds
            filename = f"{filename_prefix}_{timestamp}.png"
            screenshot_path = session_dir / filename
            
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"📸 Screenshot saved: {filename} - {description}")
            return str(screenshot_path)
        except Exception as e:
            print(f"⚠️ Failed to take screenshot {filename_prefix}: {e}")
            return None
