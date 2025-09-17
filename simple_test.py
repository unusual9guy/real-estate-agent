#!/usr/bin/env python3
"""
Simple test to check if Chrome and Selenium work properly
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def simple_test():
    """Simple test to check Chrome startup."""
    print("Testing Chrome startup...")
    
    try:
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9224")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print("Chrome started successfully!")
        print("Navigating to Google...")
        driver.get("https://www.google.com")
        
        print(f"Page title: {driver.title}")
        print("Test successful! Chrome is working.")
        
        time.sleep(3)
        driver.quit()
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        print("Chrome startup issue detected.")

if __name__ == "__main__":
    simple_test()
