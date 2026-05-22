"""Playwright-based Google Auth setup.

This script launches a visible browser to allow the user to log into Google.
Once logged in, it saves the session state (cookies, local storage) to a file.
This session can then be used by other tools to bypass complex OAuth flows.
"""
import os
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)

COOKIE_DIR = ".browser_sessions"
AUTH_FILE = os.path.join(COOKIE_DIR, "google_auth.json")

def setup_google_auth():
    Path(COOKIE_DIR).mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        print("Launching browser. Please log in to your Google account.")
        browser = p.chromium.launch(headless=False)
        
        # Load existing state if available to skip login if still valid
        context_args = {}
        if os.path.exists(AUTH_FILE):
            print("Found existing auth state, loading it...")
            context_args["storage_state"] = AUTH_FILE
            
        context = browser.new_context(**context_args)
        page = context.new_page()
        
        page.goto("https://accounts.google.com/")
        
        print("\nWaiting for login...")
        print("Please complete the login process in the browser window.")
        print("The script will detect when you are logged in and save the session.")
        
        # Wait until we are redirected away from the login page to myaccount or similar
        try:
            # Wait until the URL contains myaccount.google.com or similar successful login page
            page.wait_for_url("https://myaccount.google.com/**", timeout=300000) # 5 mins max
            print("Login successful! Saving session state...")
        except Exception:
            print("Timed out waiting for login to complete, or URL didn't match expected pattern.")
            print("Saving state anyway just in case...")
            
        context.storage_state(path=AUTH_FILE)
        print(f"Session saved to {AUTH_FILE}")
        
        browser.close()

if __name__ == "__main__":
    setup_google_auth()
