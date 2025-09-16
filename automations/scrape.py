import os, time
import json 
import random 
import selenium.webdriver.common.by as by
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def iterate_chats(driver, max_chats=None):
    chat_panel = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//div[@role='grid']"))
    )
    seen = set()
    results = []
    count = 0
    while True:
        chats = driver.find_elements(By.XPATH, "//div[@role='grid']//div[@role='row']")
        if not chats:
            break
        for c in chats:
            try:
                title_el = c.find_element(By.XPATH, ".//div[@data-testid='cell-frame-container']//span[@dir='auto']")
                title = title_el.get_attribute("title") or title_el.text
                if title in seen:
                    continue
                seen.add(title)
                driver.execute_script("arguments.scrollIntoView(true);", c)
                time.sleep(random.uniform(0.5, 1.2))
                c.click()
                time.sleep(random.uniform(0.8, 1.5))
                msgs = extract_messages_from_open_chat(driver, chat_name=title)
                results.extend(msgs)
                count += 1
                if max_chats and count >= max_chats:
                    return results
            except Exception:
                continue
        # scroll chat list further
        driver.execute_script("arguments.scrollTop = arguments.scrollHeight;", chat_panel)
        time.sleep(1.0)
    return results

def extract_messages_from_open_chat(driver, chat_name):
    # Extract right-pane message nodes; robust selectors change often – keep them configurable
    bubbles = driver.find_elements(By.XPATH, "//div[@data-testid='msg-container']")
    out = []
    for b in bubbles:
        meta = {"chat": chat_name}
        try:
            ts_el = b.find_element(By.XPATH, ".//div[@data-pre-plain-text]")
            pre = ts_el.get_attribute("data-pre-plain-text")  # like "[12:34 pm, 12/09/24] Sender: "
        except Exception:
            pre = ""
        try:
            # Plain text
            text_el = b.find_element(By.XPATH, ".//span[@dir='ltr' or @dir='auto']")
            text = text_el.text
        except Exception:
            text = ""
        # Detect media presence
        has_img = len(b.find_elements(By.XPATH, ".//img[contains(@src,'blob:')]")) > 0
        has_link = "http" in text.lower()
        meta.update({"pre": pre, "text": text, "has_img": has_img, "has_link": has_link})
        out.append(meta)
    return out