"""
JARVIS Core — Browser Automation Tools

Playwright-based browser automation for web search and browsing.
Uses Chromium (bundled with Playwright) to avoid system Chrome conflicts.
All browser tool functions return structured results.
"""

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger("jarvis.tools.browser")

# Singleton browser state
_browser = None
_context = None
_page = None

# Cached search results for follow-up result navigation
_last_search_results = []


async def check_browser_ready() -> dict:
    """Check if Playwright is installed and chromium is available."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "success": False,
            "verified": False,
            "action": "open_browser",
            "target": "playwright",
            "message": "Playwright library is not installed in the python environment.",
            "error": "Playwright library is not installed in the python environment. Please run: pip install playwright"
        }

    try:
        async with async_playwright() as p:
            # Try to launch Chromium in headless mode to verify
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        return {
            "success": True,
            "verified": True,
            "action": "open_browser",
            "target": "chromium",
            "message": "Playwright and Chromium browser binary are ready.",
            "error": None
        }
    except Exception as e:
        err_msg = str(e)
        clean_msg = "Playwright browser missing. Run: python -m playwright install chromium"
        return {
            "success": False,
            "verified": False,
            "action": "open_browser",
            "target": "chromium",
            "message": clean_msg,
            "error": err_msg
        }


async def launch_browser(headless: bool = False) -> dict:
    """Launch a Chromium browser instance."""
    global _browser, _context, _page

    if _browser and _browser.is_connected():
        url = _page.url if _page else None
        title = await _page.title() if _page else None
        return {
            "success": True,
            "verified": True,
            "action": "open_browser",
            "target": "browser",
            "message": "Browser already running.",
            "results": [],
            "url": url,
            "title": title,
            "text_preview": None,
            "error": None
        }

    # Verify readiness first
    ready = await check_browser_ready()
    if not ready["success"]:
        return ready

    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        msg = "Opened browser."

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
        
        is_active = _page is not None and _browser.is_connected()
        url = _page.url if is_active else None
        title = await _page.title() if is_active else None

        return {
            "success": is_active,
            "verified": is_active,
            "action": "open_browser",
            "target": "browser",
            "message": msg if is_active else "Failed to verify browser start.",
            "results": [],
            "url": url,
            "title": title,
            "text_preview": None,
            "error": None if is_active else "Browser is not active."
        }

    except Exception as e:
        logger.error(f"Browser launch failed: {e}")
        err_msg = str(e)
        if "Executable doesn't exist" in err_msg or "playwright install" in err_msg.lower() or "chromium" in err_msg.lower():
            clean_msg = "Playwright browser missing. Run: python -m playwright install chromium"
        else:
            clean_msg = f"Browser automation failed: {err_msg}"
        return {
            "success": False,
            "verified": False,
            "action": "open_browser",
            "target": "browser",
            "message": clean_msg,
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": err_msg
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
        return {
            "success": True,
            "verified": True,
            "action": "open_browser",
            "target": "browser",
            "message": "Browser closed.",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "action": "open_browser",
            "target": "browser",
            "message": f"Failed to close browser: {str(e)}",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": str(e)
        }


async def _ensure_page():
    """Ensure browser and page are ready."""
    global _page
    if not _page or not _browser or not _browser.is_connected():
        result = await launch_browser()
        if not result["success"]:
            raise RuntimeError(result.get("message", "Browser launch failed."))
    return _page


def is_valid_url_or_domain(text: str) -> bool:
    """Validate if the text is a valid domain or URL."""
    text = text.strip()
    if not text:
        return False
    if " " in text:
        return False
    if len(text) > 1 and text[1] == ":" and text[2] == "\\":
        return False
    pattern = r'^(https?://)?(([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?(/\S*)?$'
    return bool(re.match(pattern, text))


def is_protected_command(command: str) -> bool:
    """Check if command corresponds to a blocked dangerous browser action."""
    cmd_lower = command.lower().strip()
    
    # 1. Direct word checks
    direct_words = [
        "login", "log in", "sign in", "password", "payment", "pay ",
        "upload file", "upload", "download executable", "approve financial transaction"
    ]
    if any(word in cmd_lower for word in direct_words):
        return True

    # 2. Combination checks
    if "submit" in cmd_lower and "form" in cmd_lower:
        return True
    if "send" in cmd_lower and "message" in cmd_lower:
        return True
    if "post" in cmd_lower and "comment" in cmd_lower:
        return True
    if "approve" in cmd_lower and "transaction" in cmd_lower:
        return True

    return False


async def open_url(url: str) -> dict:
    """Navigate to a URL."""
    url = url.strip()
    
    # Check for safety / dangerous block first
    if is_protected_command(url):
        msg = "This action requires explicit confirmation and is not automated in this version."
        return {
            "success": False,
            "verified": False,
            "action": "open_url",
            "target": url,
            "message": msg,
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": msg
        }

    if not is_valid_url_or_domain(url):
        err = f"Invalid URL or domain: {url}"
        return {
            "success": False,
            "verified": False,
            "action": "open_url",
            "target": url,
            "message": err,
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": err
        }

    # Add https protocol if missing
    nav_url = url
    if not nav_url.startswith("http://") and not nav_url.startswith("https://"):
        nav_url = "https://" + nav_url

    try:
        from agent.planner import planner
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "open_url",
                "target": url,
                "message": "Navigation interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }
        
        page = await _ensure_page()
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "open_url",
                "target": url,
                "message": "Navigation interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }

        await page.goto(nav_url, wait_until="domcontentloaded", timeout=30000)
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "open_url",
                "target": url,
                "message": "Navigation interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }

        title = await page.title()
        current_url = page.url
        logger.info(f"Opened URL: {url} — {title}")
        
        return {
            "success": True,
            "verified": True,
            "action": "open_url",
            "target": url,
            "message": f"Opened {url}.",
            "results": [],
            "url": current_url,
            "title": title,
            "text_preview": None,
            "error": None
        }
    except Exception as e:
        logger.error(f"Failed to open URL: {e}")
        return {
            "success": False,
            "verified": False,
            "action": "open_url",
            "target": url,
            "message": f"Failed to open URL: {str(e)}",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": str(e)
        }


async def search_web(query: str, engine: str = "google") -> dict:
    """Search the web using the specified engine."""
    global _last_search_results
    
    if is_protected_command(query):
        msg = "This action requires explicit confirmation and is not automated in this version."
        return {
            "success": False,
            "verified": False,
            "action": "search",
            "target": query,
            "message": msg,
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": msg
        }

    search_urls = {
        "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
        "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
        "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
    }

    url = search_urls.get(engine.lower(), search_urls["google"])

    try:
        from agent.planner import planner
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "search",
                "target": query,
                "message": "Search interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }
        
        page = await _ensure_page()
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "search",
                "target": query,
                "message": "Search interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "search",
                "target": query,
                "message": "Search interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }

        await page.wait_for_timeout(2000)  # Let results load
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "search",
                "target": query,
                "message": "Search interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }

        title = await page.title()
        current_url = page.url

        # Extract search results based on engine
        raw_results = await _extract_search_results(page, engine)
        results = raw_results[:5]
        _last_search_results = results  # cache them!

        logger.info(f"Web search: '{query}' via {engine} — {len(results)} results")
        
        summary_parts = []
        for i, r in enumerate(results, 1):
            summary_parts.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
        summary = "\n\n".join(summary_parts) if results else "No structured results found."

        return {
            "success": True,
            "verified": True,
            "action": "search",
            "target": query,
            "message": f"Search completed for '{query}'.\n\n{summary}",
            "results": results,
            "url": current_url,
            "title": title,
            "text_preview": summary,
            "error": None
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {
            "success": False,
            "verified": False,
            "action": "search",
            "target": query,
            "message": f"Search failed: {str(e)}",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": str(e)
        }


async def _extract_search_results(page, engine: str) -> list[dict]:
    """Extract search results from the current page."""
    results = []

    try:
        if engine.lower() == "google":
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
                            "title": title.strip(),
                            "url": href.strip(),
                            "snippet": snippet.strip()[:200],
                        })
                except Exception:
                    continue

        elif engine.lower() == "duckduckgo":
            elements = await page.query_selector_all("article[data-testid='result']")
            for el in elements[:10]:
                try:
                    title_el = await el.query_selector("h2 a")
                    snippet_el = await el.query_selector("span[class*='snippet'], div[class*='snippet']")

                    title = await title_el.inner_text() if title_el else ""
                    href = await title_el.get_attribute("href") if title_el else ""
                    snippet = await snippet_el.inner_text() if snippet_el else ""

                    if title and href:
                        results.append({
                            "title": title.strip(),
                            "url": href.strip(),
                            "snippet": snippet.strip()[:200]
                        })
                except Exception:
                    continue

        # Fallback: extract all visible links starting with http if no structured results found
        if not results:
            links = await page.query_selector_all("a[href]")
            for link in links[:15]:
                try:
                    text = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if text and len(text) > 5 and href.startswith("http") and not any(k in href for k in ["google.com", "bing.com", "duckduckgo.com"]):
                        results.append({
                            "title": text[:100],
                            "url": href.strip(),
                            "snippet": ""
                        })
                except Exception:
                    continue

    except Exception as e:
        logger.error(f"Result extraction failed: {e}")

    return results


async def open_first_result(index: int = 0) -> dict:
    """Open result at the specified index from the last search results."""
    global _last_search_results
    if not _last_search_results:
        return {
            "success": False,
            "verified": False,
            "action": "open_first_result",
            "target": f"result at index {index}",
            "message": "No search results available. Search first.",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": "No search results available. Search first."
        }

    if index < 0 or index >= len(_last_search_results):
        index = 0

    target_result = _last_search_results[index]
    url = target_result["url"]
    
    # Navigate
    res = await open_url(url)
    res["action"] = "open_first_result"
    return res


async def get_page_content(max_chars: int = 8000) -> dict:
    """Get the title and visible text content of the current page."""
    global _page
    if not _page or not _browser or not _browser.is_connected():
        return {
            "success": False,
            "verified": False,
            "action": "extract_page",
            "target": "current_page",
            "message": "No active browser page. Open a page first.",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": "No active browser page. Open a page first."
        }

    try:
        title = await _page.title()
        url = _page.url

        # Extract visible text
        content = await _page.evaluate("""
            () => {
                const body = document.body;
                if (!body) return '';
                // Remove script and style elements
                const clone = body.cloneNode(true);
                clone.querySelectorAll('script, style, noscript, iframe, svg').forEach(el => el.remove());
                return clone.innerText || clone.textContent || '';
            }
        """)

        content = content.strip()
        truncated = len(content) > max_chars
        content_preview = content[:max_chars]

        return {
            "success": True,
            "verified": True,
            "action": "extract_page",
            "target": url,
            "message": f"Extracted text from '{title}' successfully.",
            "results": [],
            "url": url,
            "title": title,
            "text_preview": content_preview,
            "error": None
        }
    except Exception as e:
        logger.error(f"Failed to get page content: {e}")
        return {
            "success": False,
            "verified": False,
            "action": "extract_page",
            "target": "current_page",
            "message": f"Failed to get page content: {str(e)}",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": str(e)
        }


async def summarize_page(ollama_summary: bool = True) -> dict:
    """Summarize the current page using Ollama if available, otherwise return preview."""
    global _page
    if not _page or not _browser or not _browser.is_connected():
        return {
            "success": False,
            "verified": False,
            "action": "summarize_page",
            "target": "current_page",
            "message": "No active browser page. Open a page first.",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": "No active browser page. Open a page first."
        }

    content_res = await get_page_content(max_chars=8000)
    if not content_res["success"]:
        return content_res

    content_text = content_res["text_preview"]
    title = content_res["title"]
    url = content_res["url"]

    if not content_text:
        return {
            "success": True,
            "verified": True,
            "action": "summarize_page",
            "target": url,
            "message": f"The page '{title}' has no readable text content to summarize.",
            "results": [],
            "url": url,
            "title": title,
            "text_preview": "",
            "error": None
        }

    from agent.ollama_client import check_ollama_status, chat_complete
    from agent.prompts import SUMMARIZE_RESULTS_PROMPT, JARVIS_SYSTEM_PROMPT

    ollama_status = await check_ollama_status()
    if ollama_status["running"] and ollama_status["model_available"] and ollama_summary:
        try:
            prompt = SUMMARIZE_RESULTS_PROMPT.format(request=f"Summarize the webpage: '{title}'", results=content_text[:3000])
            summary = await chat_complete(
                messages=[
                    {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            if summary and not summary.startswith("[Error"):
                return {
                    "success": True,
                    "verified": True,
                    "action": "summarize_page",
                    "target": url,
                    "message": f"Summary of {title}:\n{summary}",
                    "results": [],
                    "url": url,
                    "title": title,
                    "text_preview": summary,
                    "error": None
                }
        except Exception as e:
            logger.error(f"Ollama summarization failed: {e}")

    # Fallback when Ollama is unavailable
    ollama_err = ollama_status.get("error") or "Ollama is unavailable."
    preview = content_text[:300] + "..." if len(content_text) > 300 else content_text
    msg = f"Ollama is unavailable ({ollama_err}). Here is a preview of the page '{title}':\n\n{preview}"

    return {
        "success": True,
        "verified": True,
        "action": "summarize_page",
        "target": url,
        "message": msg,
        "results": [],
        "url": url,
        "title": title,
        "text_preview": preview,
        "error": ollama_err
    }


async def click_link(text: str) -> dict:
    """Click a link on the current page by its text content."""
    try:
        from agent.planner import planner
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "click_link",
                "target": text,
                "message": "Click interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }
        page = await _ensure_page()
        if planner._interrupted:
            return {
                "success": False,
                "verified": False,
                "action": "click_link",
                "target": text,
                "message": "Click interrupted.",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": "Interrupted"
            }
        link = await page.query_selector(f"a:has-text('{text}')")
        if link:
            if planner._interrupted:
                return {
                    "success": False,
                    "verified": False,
                    "action": "click_link",
                    "target": text,
                    "message": "Click interrupted.",
                    "results": [],
                    "url": None,
                    "title": None,
                    "text_preview": None,
                    "error": "Interrupted"
                }
            await link.click()
            if planner._interrupted:
                return {
                    "success": False,
                    "verified": False,
                    "action": "click_link",
                    "target": text,
                    "message": "Click interrupted.",
                    "results": [],
                    "url": None,
                    "title": None,
                    "text_preview": None,
                    "error": "Interrupted"
                }
            await page.wait_for_load_state("domcontentloaded")
            new_title = await page.title()
            current_url = page.url
            return {
                "success": True,
                "verified": True,
                "action": "click_link",
                "target": text,
                "message": f"Clicked link '{text}', loaded page '{new_title}'.",
                "results": [],
                "url": current_url,
                "title": new_title,
                "text_preview": None,
                "error": None
            }
        else:
            return {
                "success": False,
                "verified": False,
                "action": "click_link",
                "target": text,
                "message": f"Link not found: '{text}'",
                "results": [],
                "url": None,
                "title": None,
                "text_preview": None,
                "error": f"Link not found: '{text}'"
            }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "action": "click_link",
            "target": text,
            "message": f"Click failed: {str(e)}",
            "results": [],
            "url": None,
            "title": None,
            "text_preview": None,
            "error": str(e)
        }
