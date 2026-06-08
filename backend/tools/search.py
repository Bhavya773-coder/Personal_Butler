"""
JARVIS Core — Web Search Orchestrator

High-level search tool that delegates to browser.py to perform web searches
and return structured results.
"""

import logging
from tools.browser import search_web, get_page_content, launch_browser

logger = logging.getLogger("jarvis.tools.search")


async def web_search(query: str, engine: str = "google") -> dict:
    """
    Perform a web search and return structured results.
    Automatically launches browser if needed.
    """
    # Ensure browser is running
    launch_res = await launch_browser()
    if not launch_res["success"]:
        return launch_res

    # Perform search
    return await search_web(query, engine)


async def search_and_read(query: str, result_index: int = 0) -> dict:
    """
    Search the web, open the result at result_index, and read its content.
    """
    search_res = await web_search(query)
    if not search_res["success"]:
        return search_res

    results = search_res.get("results", [])
    if not results:
        return {
            "success": False,
            "verified": False,
            "action": "search",
            "target": query,
            "message": "No search results found to read.",
            "results": [],
            "url": search_res.get("url"),
            "title": search_res.get("title"),
            "text_preview": None,
            "error": "No search results found to read."
        }

    if result_index < 0 or result_index >= len(results):
        result_index = 0

    target_result = results[result_index]
    url = target_result["url"]

    # Open URL
    from tools.browser import open_url
    open_res = await open_url(url)
    if not open_res["success"]:
        return open_res

    # Read page content
    content_res = await get_page_content()
    return content_res
