"""
JARVIS Core — Web Search Orchestrator

High-level search tool that uses browser.py to perform web searches
and return structured, summarized results.
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
    launch_result = await launch_browser()
    if "error" in launch_result:
        return launch_result

    # Perform search
    result = await search_web(query, engine)
    if "error" in result:
        return result

    # Format results for display
    results = result.get("results", [])
    if results:
        summary_parts = []
        for i, r in enumerate(results[:5], 1):
            summary_parts.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")

        result["summary"] = "\n\n".join(summary_parts)
        result["result_count"] = len(results)
    else:
        result["summary"] = f"Search completed for '{query}' but no structured results could be extracted. The page is open in the browser."

    return result


async def search_and_read(query: str, result_index: int = 0) -> dict:
    """
    Search the web, open the first result, and read its content.
    """
    search_result = await web_search(query)
    if "error" in search_result:
        return search_result

    results = search_result.get("results", [])
    if not results:
        return {"error": "No results found to read."}

    if result_index >= len(results):
        result_index = 0

    # The page should already be showing search results in the browser
    content = await get_page_content()
    return {
        "search_query": query,
        "results": results[:5],
        "page_content": content,
    }
