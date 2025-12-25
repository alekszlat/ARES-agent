"""Simple MCP test server using FastMCP.

Exposes a couple of trivial tools for testing the MCPClient:
- echo_tool(text): returns the input text unchanged.
- reverse_tool(text): returns the reversed input text.
- open_youtube_search(topic): returns a YouTube search URL for the given topic and attempts to open it in the default web browser.
"""

from itertools import count
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import logger

from urllib.parse import quote_plus

import requests
import sys
import time
import re
import anyio
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.firefox.service import Service

class TestServer:
    def __init__(self) -> None:
        self.app = FastMCP("Test Server")
        self._init_tools()

    def _init_tools(self) -> None:
        """Register example tools on the FastMCP app."""
        logger.info(f"DISPLAY={os.environ.get('DISPLAY')}")
        @self.app.tool()
        async def echo_tool(text: str) -> str:
            """Echoes the input text."""
            return text

        @self.app.tool()
        async def reverse_tool(text: str) -> str:
            """Reverses the input text."""
            return text[::-1]

        @self.app.tool()
        async def open_youtube_search(topic: str) -> str:
            """Plays a YouTube video for the given topic and returns the video URL."""
            return await anyio.to_thread.run_sync(_play_youtube_video_sync, topic)


        def _play_youtube_video_sync(topic: str, timeout: int = 15) -> str:
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

            services=Service(log_output=sys.stderr)
            driver = webdriver.Firefox(service=services)
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

    def run(self) -> None:
        """Run the MCP server over stdio."""
        logger.info("Starting TestServer over stdio")
        self.app.run(transport="stdio")


if __name__ == "__main__":
    # When launched as a script, start the stdio MCP server.
    server = TestServer()
    server.run()


