import re
import time
import requests
import sys

from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException , StaleElementReferenceException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service





def play_youtube_video(topic: str, timeout: int = 15) -> str:

    ### --------------------------------------------------------------------
    query = quote_plus(topic)
    search_url = f"https://www.youtube.com/results?search_query={query}"

    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(search_url, headers=headers, timeout=10)
    resp.raise_for_status()

    # Find first watch URL
    m = re.search(r'\"(/watch\?v=[^\"&]{11})', resp.text)
    if not m:
        raise Exception(f"No video found for topic: {topic!r}")

    watch_path = m.group(1)
    watch_url = f"https://www.youtube.com{watch_path}"

    ### --------------------------------------------------------------------


    driver = webdriver.Firefox(service=Service(log_output=sys.stderr))
    try:
        driver.get(watch_url)

        try:
            btn = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[.//span[normalize-space()='Accept all']]")
                )
            )
            btn.click()
        except TimeoutException:
            # Consent dialog didn't show up
            pass
        
        time.sleep(2)  # Wait for page to stabilize

        body = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        body.send_keys("k")
        body.send_keys("k")

        return watch_url
    except Exception as e:
        raise e


if __name__ == "__main__":
    input_topic = input("Enter a topic to search on YouTube: ")
    topic = input_topic.strip()
    video_url = play_youtube_video(topic)
    print(f"Video URL: {video_url}")
