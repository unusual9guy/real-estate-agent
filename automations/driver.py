from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os, time

def make_driver(headless=True, user_data_dir="./automation/user_data"):
    opts = Options()
    if headless:
        # For first login, run non-headless; after QR pairing works, headless can be tried
        # Many WhatsApp Web flows work better non-headless; prefer headed + virtual display on server
        pass
    opts.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
    driver.get("https://web.whatsapp.com")
    return driver

def wait_for_ready(driver, timeout=120):
    # Wait for search input or chat list to render – indicates logged-in state
    t0 = time.time()
    while time.time() - t0 < timeout:
        if "WhatsApp" in driver.title:
            # simple signal; you can also use WebDriverWait with a robust selector
            return True
        time.sleep(2)
    return False