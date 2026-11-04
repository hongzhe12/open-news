from mcp.server import MCPServer

from .api import search_and_get_async

mcp = MCPServer(
    "Open News Search",
    instructions=(
        "Search Chinese news across multiple public sources. "
        "Results are deduplicated and ranked by title relevance. "
        "Use days to limit known publication dates; undated articles are retained."
    ),
)


@mcp.tool()
async def search_news(
    query: str,
    limit: int = 20,
    days: int | None = None,
) -> list[dict]:
    """Search Chinese news and return titles, sources, dates, URLs, and summaries."""
    return await search_and_get_async(query, limit, days)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
