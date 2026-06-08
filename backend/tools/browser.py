"""
JARVIS Core — Browser Automation Tools

Playwright-based browser automation for web search and browsing.
Uses Chromium (bundled with Playwright) to avoid system Chrome conflicts.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("jarvis.tools.browser")

# Singleton browser state
_browser = None
_context = None
_page = None


async def launch_browser(headless: bool = False) -> dict:
    """Launch a Chromium browser instance."""
    global _browser, _context, _page

    if _browser and _browser.is_connected():
        return {"success": True, "message": "Browser already running."}

    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        
        try:
            # Try launching system Chrome first
            _browser = await pw.chromium.launch(
                headless=headless,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            logger.info("Launched system Google Chrome via Playwright")
        except Exception as chrome_err:
            logger.info(f"System Chrome launch failed ({chrome_err}), falling back to bundled Chromium")
            # Fallback to bundled Playwright Chromium
            _browser = await pw.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            logger.info("Launched bundled Chromium via Playwright")

        _context = await _browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        _page = await _context.new_page()

        logger.info("Browser launched successfully")
        return {"success": True, "message": "Browser launched."}

    except ImportError:
        logger.error("Playwright library is not installed in the python environment.")
        return {
            "error": "Browser automation failed: Playwright library is not installed in the python environment. Please run: pip install playwright"
        }
    except Exception as e:
        logger.error(f"Browser launch failed: {e}")
        err_msg = str(e)
        if "Executable doesn't exist" in err_msg or "playwright install" in err_msg.lower() or "chromium" in err_msg.lower():
            return {"error": "Playwright browser missing. Run: python -m playwright install chromium"}
        return {
            "error": f"Browser automation failed: {err_msg}. "
            "Check Playwright installation. Make sure Chromium is installed by running: playwright install chromium"
        }


async def close_browser() -> dict:
    """Close the browser instance."""
    global _browser, _context, _page

    try:
        if _browser:
            await _browser.close()
        _browser = None
        _context = None
        _page = None
        logger.info("Browser closed")
        return {"success": True}
    except Exception as e:
        return {"error": f"Failed to close browser: {str(e)}"}


async def _ensure_page():
    """Ensure browser and page are ready."""
    global _page
    if not _page or not _browser or not _browser.is_connected():
        result = await launch_browser()
        if "error" in result:
            raise RuntimeError(result["error"])
    return _page


async def open_url(url: str) -> dict:
    """Navigate to a URL."""
    try:
        from agent.planner import planner
        if planner._interrupted:
            return {"error": "Interrupted"}
        page = await _ensure_page()
        if planner._interrupted:
            return {"error": "Interrupted"}
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if planner._interrupted:
            return {"error": "Interrupted"}
        title = await page.title()
        logger.info(f"Opened URL: {url} — {title}")
        return {"success": True, "url": url, "title": title}
    except Exception as e:
        return {"error": f"Failed to open URL: {str(e)}"}


async def search_web(query: str, engine: str = "google") -> dict:
    """Search the web using the specified engine."""
    search_urls = {
        "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
        "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
        "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
    }

    url = search_urls.get(engine.lower(), search_urls["google"])

    try:
        from agent.planner import planner
        if planner._interrupted:
            return {"error": "Interrupted"}
        page = await _ensure_page()
        if planner._interrupted:
            return {"error": "Interrupted"}
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if planner._interrupted:
            return {"error": "Interrupted"}
        await page.wait_for_timeout(2000)  # Let results load
        if planner._interrupted:
            return {"error": "Interrupted"}

        title = await page.title()

        # Extract search results based on engine
        results = await _extract_search_results(page, engine)

        logger.info(f"Web search: '{query}' via {engine} — {len(results)} results")
        return {
            "success": True,
            "query": query,
            "engine": engine,
            "page_title": title,
            "results": results,
        }
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


async def _extract_search_results(page, engine: str) -> list[dict]:
    """Extract search results from the current page."""
    results = []

    try:
        if engine.lower() == "google":
            # Google search results
            elements = await page.query_selector_all("div.g")
            for el in elements[:10]:
                try:
                    title_el = await el.query_selector("h3")
                    link_el = await el.query_selector("a")
                    snippet_el = await el.query_selector("div[data-sncf], div.VwiC3b, span.aCOpRe")

                    title = await title_el.inner_text() if title_el else ""
                    href = await link_el.get_attribute("href") if link_el else ""
                    snippet = await snippet_el.inner_text() if snippet_el else ""

                    if title and href:
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet[:200],
                        })
                except Exception:
                    continue

        elif engine.lower() == "duckduckgo":
            elements = await page.query_selector_all("article[data-testid='result']")
            for el in elements[:10]:
                try:
                    title_el = await el.query_selector("h2 a")
                    snippet_el = await el.query_selector("span[class*='snippet']")

                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    snippet = await snippet_el.inner_text() if snippet_el else ""

                    if title:
                        results.append({"title": title, "url": href or "", "snippet": snippet[:200]})
                except Exception:
                    continue

        # Fallback: extract all visible links if no structured results found
        if not results:
            links = await page.query_selector_all("a[href]")
            for link in links[:15]:
                try:
                    text = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if text and len(text) > 5 and href.startswith("http"):
                        results.append({"title": text[:100], "url": href, "snippet": ""})
                except Exception:
                    continue

    except Exception as e:
        logger.error(f"Result extraction failed: {e}")

    return results


async def get_page_content(max_chars: int = 5000) -> dict:
    """Get the title and visible text content of the current page."""
    try:
        page = await _ensure_page()
        title = await page.title()
        url = page.url

        # Extract visible text
        content = await page.evaluate("""
            () => {
                const body = document.body;
                if (!body) return '';
                // Remove script and style elements
                const clone = body.cloneNode(true);
                clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
                return clone.innerText || clone.textContent || '';
            }
        """)

        content = content.strip()[:max_chars]

        return {
            "title": title,
            "url": url,
            "content": content,
            "truncated": len(content) >= max_chars,
        }
    except Exception as e:
        return {"error": f"Failed to get page content: {str(e)}"}


async def click_link(text: str) -> dict:
    """Click a link on the current page by its text content."""
    try:
        from agent.planner import planner
        if planner._interrupted:
            return {"error": "Interrupted"}
        page = await _ensure_page()
        if planner._interrupted:
            return {"error": "Interrupted"}
        link = await page.query_selector(f"a:has-text('{text}')")
        if link:
            if planner._interrupted:
                return {"error": "Interrupted"}
            await link.click()
            if planner._interrupted:
                return {"error": "Interrupted"}
            await page.wait_for_load_state("domcontentloaded")
            new_title = await page.title()
            return {"success": True, "clicked": text, "new_page_title": new_title}
        else:
            return {"error": f"Link not found: '{text}'"}
    except Exception as e:
        return {"error": f"Click failed: {str(e)}"}
