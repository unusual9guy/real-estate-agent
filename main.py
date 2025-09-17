#!/usr/bin/env python3
"""
WhatsApp Web Message Extractor

Quick usage:
  pip install -r requirements.txt
  python main.py --chat 'Group Name'
  python main.py  (to iterate visible chats)

Requirements:
  selenium
  webdriver-manager
  pandas
  python-dotenv
  tenacity
"""

import argparse
import csv
import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# WhatsApp Web selectors - update these if the UI changes
SELECTORS = {
    # Main containers - multiple fallbacks for robustness
    'chat_list_container': [
        "//div[@role='grid']",
        "//div[@data-testid='chat-list']",
        "//div[contains(@class, 'chat-list')]",
        "//div[@role='application']//div[@role='grid']"
    ],
    'chat_list_rows': [
        "//div[@role='row']",
        "//div[contains(@class, 'chat')]",
        "//div[@data-testid='chat-list']//div[contains(@class, 'row')]"
    ],
    'message_container': [
        "//div[@data-testid='msg-container']",
        "//div[contains(@class, 'message')]",
        "//div[@data-testid='conversation-panel-messages']//div[contains(@class, 'message')]"
    ],
    'chat_title': [
        "//header//span[@data-testid='conversation-title']",
        "//header//span[contains(@class, 'title')]",
        "//div[@data-testid='conversation-header']//span"
    ],
    
    # Message elements
    'message_bubble': [
        "//div[contains(@class, 'message-in') or contains(@class, 'message-out')]",
        "//div[contains(@class, 'message')]"
    ],
    'message_text': [
        ".//span[@dir='auto' or @dir='ltr']",
        ".//span[contains(@class, 'selectable-text')]",
        ".//div[contains(@class, 'selectable-text')]"
    ],
    'message_metadata': [
        ".//div[@data-pre-plain-text]",
        ".//div[contains(@class, 'message-time')]"
    ],
    'message_sender': [
        ".//span[@class='quoted-mention' or contains(@class, 'quoted-mention')]",
        ".//span[contains(@class, 'sender')]"
    ],
    
    # Search and navigation
    'search_box': [
        "//div[@data-testid='search']//input",
        "//input[@data-testid='search-input']",
        "//div[contains(@class, 'search')]//input"
    ],
    'search_results': [
        "//div[@data-testid='search-results']",
        "//div[contains(@class, 'search-results')]"
    ],
    
    # Media detection
    'media_elements': [
        ".//img | .//video | .//div[contains(@class, 'document')] | .//div[contains(@class, 'audio')]",
        ".//img | .//video | .//div[contains(@class, 'media')]"
    ],
    
    # Loading indicators
    'loading_spinner': [
        "//div[@data-testid='loading-spinner']",
        "//div[contains(@class, 'loading')]"
    ],
    'qr_code': [
        "//div[@data-testid='qr-code']",
        "//canvas[@data-testid='qr-code']",
        "//div[contains(@class, 'qr')]"
    ],
}


class WhatsAppExtractor:
    def __init__(self, user_data_dir: str = "./user_data", headless: bool = False):
        self.user_data_dir = Path(user_data_dir)
        self.headless = headless
        self.driver = None
        self.wait = None
        
    def find_element_with_fallbacks(self, selector_key: str, timeout: int = 10):
        """Find element using multiple selector fallbacks."""
        selectors = SELECTORS.get(selector_key, [])
        if isinstance(selectors, str):
            selectors = [selectors]
            
        for selector in selectors:
            try:
                if selector and isinstance(selector, str):  # Ensure selector is a valid string
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements and elements[0].is_displayed():
                        return elements[0]
            except Exception as e:
                print(f"Selector failed: {selector} - {e}")
                continue
        return None
        
    def find_elements_with_fallbacks(self, selector_key: str):
        """Find elements using multiple selector fallbacks."""
        selectors = SELECTORS.get(selector_key, [])
        if isinstance(selectors, str):
            selectors = [selectors]
            
        for selector in selectors:
            try:
                if selector and isinstance(selector, str):  # Ensure selector is a valid string
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        return elements
            except Exception as e:
                print(f"Selector failed: {selector} - {e}")
                continue
        return []
        
    def setup_driver(self) -> None:
        """Initialize Chrome WebDriver with persistent user profile."""
        chrome_options = Options()
        
        # Use minimal options that work on this system
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Add user data directory only if not headless (to avoid conflicts)
        if not self.headless:
            # Ensure user data directory exists with proper permissions
            self.user_data_dir.mkdir(parents=True, exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={self.user_data_dir.absolute()}")
            print(f"Using user data directory: {self.user_data_dir.absolute()}")
        
        # Add headless mode if requested
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Use random debugging port to avoid conflicts
        chrome_options.add_argument("--remote-debugging-port=0")
        
        # Initialize WebDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Set up wait with longer timeout
        self.wait = WebDriverWait(self.driver, 15)
        
    def random_sleep(self, min_seconds: float = 0.5, max_seconds: float = 1.2) -> None:
        """Random sleep between interactions."""
        time.sleep(random.uniform(min_seconds, max_seconds))
        
    def handle_qr_code(self) -> None:
        """Handle QR code scanning if needed."""
        try:
            # Wait a bit for the page to load
            self.random_sleep(3, 5)
            
            # Check if QR code is present and visible
            qr_elements = self.find_elements_with_fallbacks('qr_code')
            if qr_elements and qr_elements[0].is_displayed():
                print("Scan the WhatsApp Web QR code, then press Enter...")
                input()
                
                # Wait for QR to disappear and interface to load
                print("Waiting for WhatsApp Web to load...")
                max_wait_time = 30  # Wait up to 30 seconds
                start_time = time.time()
                
                while time.time() - start_time < max_wait_time:
                    try:
                        # Check if QR code is gone and chat list is present
                        qr_elements = self.find_elements_with_fallbacks('qr_code')
                        chat_list = self.find_elements_with_fallbacks('chat_list_container')
                        
                        if (not qr_elements or not qr_elements[0].is_displayed()) and chat_list:
                            print("WhatsApp Web loaded successfully!")
                            return
                            
                    except Exception:
                        pass
                    
                    time.sleep(1)
                
                # If we get here, try to continue anyway
                print("QR code handling completed, continuing...")
                
        except Exception as e:
            print(f"QR code handling: {e}")
            # Continue anyway, might already be logged in
            
    def navigate_to_whatsapp(self) -> None:
        """Navigate to WhatsApp Web and handle login."""
        print("Navigating to WhatsApp Web...")
        self.driver.get("https://web.whatsapp.com")
        self.random_sleep(2, 3)
        
        # Handle QR code if needed
        self.handle_qr_code()
        
        # Wait for main interface to load with more flexible approach
        print("Waiting for WhatsApp Web interface to load...")
        max_attempts = 20
        for attempt in range(max_attempts):
            try:
                # Try to find chat list using fallback selectors
                chat_list = self.find_element_with_fallbacks('chat_list_container')
                if chat_list:
                    print("WhatsApp Web interface loaded successfully!")
                    return
                
                # Also check if we're on the main page (not QR page)
                if "web.whatsapp.com" in self.driver.current_url and "qr" not in self.driver.current_url.lower():
                    # Try to find any chat-related elements
                    chat_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'chat') or contains(@data-testid, 'chat')]")
                    if chat_elements:
                        print("WhatsApp Web interface loaded successfully!")
                        return
                
            except Exception as e:
                print(f"Attempt {attempt + 1}/{max_attempts}: {e}")
            
            time.sleep(2)
        
        # If we get here, try to continue anyway - might still work
        print("Interface loading timeout, but continuing...")
        print("If extraction fails, try running with --headless false to see what's happening")
            
    def find_chat_by_name(self, chat_name: str) -> bool:
        """Find and open a specific chat by name."""
        print(f"Searching for chat: {chat_name}")
        
        try:
            # Click search box
            search_box = self.wait.until(EC.element_to_be_clickable((By.XPATH, SELECTORS['search_box'])))
            search_box.click()
            self.random_sleep(0.5, 1.0)
            
            # Type chat name
            search_box.clear()
            search_box.send_keys(chat_name)
            self.random_sleep(1, 2)
            
            # Look for exact match in search results
            search_results = self.driver.find_elements(By.XPATH, SELECTORS['search_results'])
            for result in search_results:
                try:
                    result_text = result.text.strip()
                    if result_text == chat_name:
                        result.click()
                        self.random_sleep(1, 2)
                        return True
                except (ElementClickInterceptedException, NoSuchElementException):
                    continue
                    
            # If not found in search results, try clicking first result
            if search_results:
                search_results[0].click()
                self.random_sleep(1, 2)
                return True
                
            return False
            
        except (NoSuchElementException, TimeoutException) as e:
            print(f"Error finding chat '{chat_name}': {e}")
            return False
            
    def get_chat_title(self) -> str:
        """Get the current chat title."""
        try:
            title_element = self.find_element_with_fallbacks('chat_title')
            if title_element:
                return title_element.text.strip()
            return "Unknown Chat"
        except Exception as e:
            print(f"Error getting chat title: {e}")
            return "Unknown Chat"
            
    def get_all_visible_chats(self) -> List[str]:
        """Get list of all visible chat names in the left pane."""
        chat_names = []
        try:
            # Scroll to top first
            chat_list = self.find_element_with_fallbacks('chat_list_container')
            if chat_list:
                self.driver.execute_script("arguments[0].scrollTop = 0;", chat_list)
                self.random_sleep(1, 2)
            
            # Get initial visible chats
            chat_rows = self.find_elements_with_fallbacks('chat_list_rows')
            
            for row in chat_rows:
                try:
                    # Try to get chat name from the row
                    chat_name_elements = row.find_elements(By.XPATH, ".//span[@title]")
                    if chat_name_elements:
                        chat_name = chat_name_elements[0].get_attribute('title')
                        if chat_name and chat_name not in chat_names:
                            chat_names.append(chat_name)
                except (NoSuchElementException, Exception) as e:
                    print(f"Error getting chat name: {e}")
                    continue
                    
            return chat_names
            
        except Exception as e:
            print(f"Error getting visible chats: {e}")
            return []
            
    def extract_messages_from_chat(self, chat_name: str) -> List[Dict]:
        """Extract all messages from the currently open chat."""
        messages = []
        
        try:
            # Wait for messages to load
            self.random_sleep(1, 2)
            
            # Get all message containers
            message_containers = self.driver.find_elements(By.XPATH, SELECTORS['message_container'])
            
            for container in message_containers:
                try:
                    message_data = self.parse_message(container, chat_name)
                    if message_data:
                        messages.append(message_data)
                except Exception as e:
                    print(f"Error parsing message: {e}")
                    continue
                    
        except NoSuchElementException:
            print(f"No messages found in chat: {chat_name}")
            
        return messages
        
    def parse_message(self, container, chat_name: str) -> Optional[Dict]:
        """Parse a single message container into structured data."""
        try:
            # Initialize message data
            message_data = {
                'chat_name': chat_name,
                'sender': '',
                'text': '',
                'timestamp': '',
                'has_media': False
            }
            
            # Check for media
            media_elements = container.find_elements(By.XPATH, SELECTORS['media_elements'])
            message_data['has_media'] = len(media_elements) > 0
            
            # Try to get metadata from data-pre-plain-text
            metadata_elements = container.find_elements(By.XPATH, SELECTORS['message_metadata'])
            if metadata_elements:
                metadata = metadata_elements[0].get_attribute('data-pre-plain-text')
                if metadata:
                    # Parse metadata: "[time, date] Sender:"
                    match = re.match(r'\[(\d{1,2}:\d{2}(?::\d{2})?),\s*(\d{1,2}/\d{1,2}/\d{4})\]\s*(.+?):', metadata)
                    if match:
                        time_str, date_str, sender = match.groups()
                        message_data['timestamp'] = f"{date_str} {time_str}"
                        message_data['sender'] = sender.strip()
            
            # Get message text
            text_elements = container.find_elements(By.XPATH, SELECTORS['message_text'])
            if text_elements:
                message_data['text'] = ' '.join([elem.text.strip() for elem in text_elements if elem.text.strip()])
            
            # If no sender found from metadata, try to infer from message direction
            if not message_data['sender']:
                # Check if it's an outgoing message (from me)
                if 'message-out' in container.get_attribute('class'):
                    message_data['sender'] = 'Me'
                else:
                    # For incoming messages, try to get sender from bubble header
                    sender_elements = container.find_elements(By.XPATH, SELECTORS['message_sender'])
                    if sender_elements:
                        message_data['sender'] = sender_elements[0].text.strip()
                    else:
                        message_data['sender'] = 'Unknown'
            
            return message_data
            
        except Exception as e:
            print(f"Error parsing message: {e}")
            return None
            
    def save_to_csv(self, messages: List[Dict], output_path: str) -> None:
        """Save messages to CSV file."""
        if not messages:
            print("No messages to save")
            return
            
        df = pd.DataFrame(messages)
        df = df[['chat_name', 'sender', 'text', 'timestamp', 'has_media']]  # Ensure column order
        df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"Saved {len(messages)} messages to {output_path}")
        
    def save_to_jsonl(self, messages: List[Dict], output_path: str) -> None:
        """Save messages to JSONL file."""
        if not messages:
            print("No messages to save")
            return
            
        with open(output_path, 'w', encoding='utf-8') as f:
            for message in messages:
                f.write(json.dumps(message, ensure_ascii=False) + '\n')
        print(f"Saved {len(messages)} messages to {output_path}")
        
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system usage."""
        return re.sub(r'[<>:"/\\|?*]', '_', filename)
        
    def create_output_directory(self) -> str:
        """Create output directory with current date."""
        today = datetime.now().strftime("%Y-%m-%d")
        output_dir = Path(f"./output/{today}")
        output_dir.mkdir(parents=True, exist_ok=True)
        return str(output_dir)
        
    def extract_single_chat(self, chat_name: str) -> None:
        """Extract messages from a single chat."""
        print(f"Extracting messages from chat: {chat_name}")
        
        if not self.find_chat_by_name(chat_name):
            print(f"Chat '{chat_name}' not found")
            return
            
        # Get actual chat title (might be different from search term)
        actual_chat_name = self.get_chat_title()
        print(f"Opened chat: {actual_chat_name}")
        
        # Extract messages
        messages = self.extract_messages_from_chat(actual_chat_name)
        
        if not messages:
            print("No messages found")
            return
            
        # Create output directory
        output_dir = self.create_output_directory()
        
        # Save to files
        sanitized_name = self.sanitize_filename(actual_chat_name)
        csv_path = f"{output_dir}/messages_{sanitized_name}.csv"
        jsonl_path = f"{output_dir}/messages_{sanitized_name}.jsonl"
        
        self.save_to_csv(messages, csv_path)
        self.save_to_jsonl(messages, jsonl_path)
        
    def extract_all_chats(self, max_chats: Optional[int] = None) -> None:
        """Extract messages from all visible chats."""
        print("Extracting messages from all visible chats...")
        
        # Get list of all visible chats
        chat_names = self.get_all_visible_chats()
        
        if not chat_names:
            print("No visible chats found")
            return
            
        if max_chats:
            chat_names = chat_names[:max_chats]
            
        print(f"Found {len(chat_names)} chats to process")
        
        all_messages = []
        processed_chats = 0
        
        for chat_name in chat_names:
            try:
                print(f"Processing chat {processed_chats + 1}/{len(chat_names)}: {chat_name}")
                
                if self.find_chat_by_name(chat_name):
                    actual_chat_name = self.get_chat_title()
                    messages = self.extract_messages_from_chat(actual_chat_name)
                    
                    if messages:
                        all_messages.extend(messages)
                        print(f"  Extracted {len(messages)} messages")
                    else:
                        print(f"  No messages found")
                        
                    processed_chats += 1
                    self.random_sleep(1, 2)
                else:
                    print(f"  Failed to open chat: {chat_name}")
                    
            except Exception as e:
                print(f"  Error processing chat '{chat_name}': {e}")
                continue
                
        if not all_messages:
            print("No messages extracted from any chat")
            return
            
        # Create output directory
        output_dir = self.create_output_directory()
        
        # Save to files
        csv_path = f"{output_dir}/messages_all.csv"
        jsonl_path = f"{output_dir}/messages_all.jsonl"
        
        self.save_to_csv(all_messages, csv_path)
        self.save_to_jsonl(all_messages, jsonl_path)
        
        print(f"Total: {len(all_messages)} messages from {processed_chats} chats")
        
    def run(self, chat_name: Optional[str] = None, max_chats: Optional[int] = None, debug: bool = False) -> None:
        """Main execution method."""
        try:
            self.setup_driver()
            self.navigate_to_whatsapp()
            
            if chat_name:
                self.extract_single_chat(chat_name)
            else:
                self.extract_all_chats(max_chats)
                
        except Exception as e:
            print(f"Error: {e}")
            if debug:
                print("Debug mode: Browser will remain open")
                input("Press Enter to close browser...")
        finally:
            if self.driver and not debug:
                self.driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Extract messages from WhatsApp Web")
    parser.add_argument("--chat", help="Specific chat or group name to extract")
    parser.add_argument("--user-data", default="./user_data", help="Chrome user data directory (default: ./user_data)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--max-chats", type=int, help="Maximum number of chats to process in all-chats mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with verbose output")
    
    args = parser.parse_args()
    
    if args.debug:
        print("Debug mode enabled - browser will stay open for inspection")
        print("Press Ctrl+C to exit after extraction")
    
    extractor = WhatsAppExtractor(
        user_data_dir=args.user_data,
        headless=args.headless
    )
    
    try:
        extractor.run(chat_name=args.chat, max_chats=args.max_chats, debug=args.debug)
    except KeyboardInterrupt:
        print("\nExtraction interrupted by user")
    except Exception as e:
        print(f"Error during extraction: {e}")
        if args.debug:
            print("Browser will remain open for debugging")
            input("Press Enter to close browser...")
    finally:
        if not args.debug and extractor.driver:
            extractor.driver.quit()


if __name__ == "__main__":
    main()


# Troubleshooting comments:
# 
# If the script can't find elements, update the SELECTORS constants at the top of the file.
# WhatsApp Web UI changes frequently, so selectors may need updates.
#
# To re-scan QR code:
# 1. Close all Chrome instances
# 2. Delete the user-data directory: rm -rf ./user_data (Windows: rmdir /s user_data)
# 3. Run the script again
#
# If rendering issues occur, set --headless false to see the browser window.
#
# For debugging loading issues:
# 1. Run with --debug flag: python main.py --debug
# 2. Or use the test script: python test_whatsapp.py
# 3. Check if WhatsApp Web loads manually in a regular browser
#
# Common issues:
# - "Chat not found": Verify the exact chat name, including capitalization and special characters
# - "No messages found": The chat might be empty or messages might not have loaded yet
# - "Failed to load WhatsApp Web": Check internet connection and try again
# - "Interface loading timeout": Try running with --debug to see what's happening
# - Browser closes unexpectedly: Use --debug mode or check Chrome version compatibility
