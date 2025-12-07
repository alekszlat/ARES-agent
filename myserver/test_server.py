"""Simple MCP test server using FastMCP.

Exposes a couple of trivial tools for testing the MCPClient:
- echo_tool(text): returns the input text unchanged.
- reverse_tool(text): returns the reversed input text.
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import logger


class TestServer:
    def __init__(self) -> None:
        # Create the FastMCP application with a human-readable name.
        self.app = FastMCP("Test Server")
        self._init_tools()

    def _init_tools(self) -> None:
        """Register example tools on the FastMCP app."""

        @self.app.tool()
        async def echo_tool(text: str) -> str:
            """Echoes the input text."""
            return text

        @self.app.tool()
        async def reverse_tool(text: str) -> str:
            """Reverses the input text."""
            return text[::-1]

    def run(self) -> None:
        """Run the MCP server over stdio."""
        logger.info("Starting TestServer over stdio")
        self.app.run(transport="stdio")


if __name__ == "__main__":
    # When launched as a script, start the stdio MCP server.
    server = TestServer()
    server.run()
