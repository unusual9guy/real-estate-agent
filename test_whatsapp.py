#!/usr/bin/env python3
"""
Simple test script to debug WhatsApp Web loading issues
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def test_whatsapp_loading():
    """Test WhatsApp Web loading with debug output."""
    print("Setting up Chrome driver...")
    
    # Create user data directory with absolute path
    import os
    user_data_dir = os.path.abspath("./user_data")
    os.makedirs(user_data_dir, exist_ok=True)
    print(f"Using user data directory: {user_data_dir}")
    
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    chrome_options.add_argument("--remote-debugging-port=0")  # Use random port
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        print("Navigating to WhatsApp Web...")
        driver.get("https://web.whatsapp.com")
        
        print("Waiting 10 seconds for page to load...")
        time.sleep(10)
        
        print(f"Current URL: {driver.current_url}")
        print(f"Page title: {driver.title}")
        
        # Check for QR code
        qr_elements = driver.find_elements(By.XPATH, "//div[@data-testid='qr-code'] | //canvas[@data-testid='qr-code']")
        if qr_elements:
            print("QR code found - scan it with your phone")
            input("Press Enter after scanning QR code...")
        
        # Wait for interface to load
        print("Waiting for interface to load...")
        time.sleep(5)
        
        # Try to find chat list
        selectors_to_try = [
            "//div[@role='grid']",
            "//div[@data-testid='chat-list']",
            "//div[contains(@class, 'chat-list')]",
            "//div[@role='application']//div[@role='grid']"
        ]
        
        chat_list_element = None
        for i, selector in enumerate(selectors_to_try):
            elements = driver.find_elements(By.XPATH, selector)
            print(f"Selector {i+1}: {selector} - Found {len(elements)} elements")
            if elements and elements[0].is_displayed():
                chat_list_element = elements[0]
                print(f"  Using this selector for chat list")
                break
        
        if chat_list_element:
            print("Scrolling through chat list to load all chats...")
            
            # Scroll to load more chats
            last_height = driver.execute_script("return arguments[0].scrollHeight", chat_list_element)
            scroll_attempts = 0
            max_scrolls = 5
            
            while scroll_attempts < max_scrolls:
                # Scroll down
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", chat_list_element)
                time.sleep(2)
                
                # Check if new content loaded
                new_height = driver.execute_script("return arguments[0].scrollHeight", chat_list_element)
                if new_height == last_height:
                    break
                last_height = new_height
                scroll_attempts += 1
                print(f"  Scroll {scroll_attempts}: Loaded more content")
            
            # Now get all chat rows
            chat_rows = driver.find_elements(By.XPATH, "//div[@role='row']")
            print(f"Found {len(chat_rows)} total chat rows after scrolling")
            
            # Extract chat names
            chat_names = []
            for i, row in enumerate(chat_rows[:10]):  # Limit to first 10 for testing
                try:
                    # Try to get chat name
                    name_elements = row.find_elements(By.XPATH, ".//span[@title]")
                    if name_elements:
                        chat_name = name_elements[0].get_attribute('title')
                        if chat_name and chat_name not in chat_names:
                            chat_names.append(chat_name)
                            print(f"  Chat {i+1}: {chat_name}")
                except Exception as e:
                    print(f"  Error getting chat name for row {i+1}: {e}")
            
            print(f"Total unique chats found: {len(chat_names)}")
        
        # Check for any chat-related elements
        chat_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'chat') or contains(@data-testid, 'chat')]")
        print(f"Found {len(chat_elements)} chat-related elements")
        
        print("Test completed. Browser will remain open for inspection.")
        input("Press Enter to close browser...")
        
    except Exception as e:
        print(f"Error: {e}")
        input("Press Enter to close browser...")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_whatsapp_loading()
