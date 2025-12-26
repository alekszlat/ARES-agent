"""Simple MCP test server using FastMCP.

Exposes a couple of trivial tools for testing the MCPClient:
- echo_tool(text): returns the input text unchanged.
- reverse_tool(text): returns the reversed input text.
- open_youtube_search(topic): returns a YouTube search URL for the given topic and attempts to open it in the default web browser.
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import logger

from urllib.parse import quote_plus

import requests
import re
import anyio
import os

import webbrowser as web

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


        def _play_youtube_video_sync(topic: str, tout: int = 10) -> str:
            ### --------------------------------------------------------------------
            query = quote_plus(topic)
            search_url = f"https://www.youtube.com/results?search_query={query}"

            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(search_url, headers=headers, timeout=tout)
            resp.raise_for_status()

            # Find first watch URL
            m = re.search(r'\"(/watch\?v=[^\"&]{11})', resp.text)
            if not m:
                raise Exception(f"No video found for topic: {topic!r}")

            watch_path = m.group(1)
            watch_url = f"https://www.youtube.com{watch_path}"

            ### --------------------------------------------------------------------

            try:
                web.open(watch_url, new=2)
                return watch_url
            except Exception as e:
                logger.error(f"Error opening YouTube video: {e}")
                return ""

    def run(self) -> None:
        """Run the MCP server over stdio."""
        logger.info("Starting TestServer over stdio")
        self.app.run(transport="stdio")


if __name__ == "__main__":
    # When launched as a script, start the stdio MCP server.
    server = TestServer()
    server.run()


