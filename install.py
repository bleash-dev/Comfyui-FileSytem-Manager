import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    
    if os.path.exists(requirements_path):
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-r", requirements_path
            ])
            print("✅ FileSystem Manager dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install dependencies: {e}")
            return False
    else:
        print("⚠️ requirements.txt not found")
    
    return True

def install_playwright_browsers():
    """Install Playwright browsers"""
    try:
        print("Installing Playwright browsers for File System Manager (Google Drive Upload)...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Playwright browsers installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install Playwright browsers: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Failed to install Playwright browsers: playwright command not found. Make sure playwright is installed correctly.")
        return False
    return True

if __name__ == "__main__":
    if install_requirements():
        install_playwright_browsers()
