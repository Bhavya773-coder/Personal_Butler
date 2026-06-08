"""
JARVIS Core — Intent Router

Classifies user messages into task categories and routes to appropriate handlers.
Uses Ollama for intent classification with structured prompt.
"""

import logging
import json
import re
from agent.ollama_client import chat_complete
from agent.prompts import INTENT_CLASSIFICATION_PROMPT

logger = logging.getLogger("jarvis.agent.router")

# Quick keyword-based classification (faster than LLM for obvious intents)
KEYWORD_PATTERNS: dict[str, list[str]] = {
    "browser": [
        "search chrome", "browse", "search for", "search the web",
        "google", "search google", "open url", "open website", "search bing",
        "search duckduckgo", "web search", "look up online", "search online",
        "youtube.com", "open youtube", ".com", ".org", ".net",
        "http://", "https://", "go to", "navigate to", "first result",
        "summarize this page", "summarize this website", "summarize page",
        "summarize this",
    ],
    "filesystem": [
        "create folder", "create a folder", "make folder", "make a folder",
        "list files", "search files", "find files", "read file",
        "copy file", "move file", "rename file", "delete file",
        "search downloads", "search desktop", "search documents",
        "find pdf", "find document", "open folder", "list folder",
        "what files", "show files", "search my", "downloads folder",
        "desktop folder", "documents folder", "find files named", "read this",
        "list files in",
    ],
    "pc_control": [
        "open notepad", "open calculator", "open calc", "open paint",
        "open explorer", "open task manager", "open app", "open application",
        "launch", "take screenshot", "type text", "press key",
        "open word", "open excel", "open vscode", "open vs code", "open spotify",
        "open discord", "open settings", "open edge", "open firefox",
        "open downloads", "open desktop", "open documents",
        "open the notepad", "please open notepad", "launch notepad", "start notepad", "run notepad",
        "can you open the notepad", "please open calculator", "start calculator",
        "open chrome", "please open chrome", "start chrome", "please open downloads", "start downloads",
        "please open desktop", "start desktop"
    ],
    "system_info": [
        "cpu", "ram", "memory", "disk", "system info", "system status",
        "how much memory", "processor", "usage", "disk space",
        "storage", "battery", "uptime", "free disk", "free space",
    ],
}

# Intent → response when action is a stop/interrupt
STOP_WORDS = {"stop", "cancel", "abort", "interrupt", "halt", "enough", "shut up", "be quiet", "nevermind", "never mind", "wait", "pause"}


def quick_classify(message: str) -> str | None:
    """
    Fast keyword-based intent classification.
    Returns None if no confident match (falls through to LLM).
    """
    msg_lower = message.lower().strip()

    # Check for stop commands
    if msg_lower in STOP_WORDS or msg_lower.startswith("stop"):
        return "interrupt"

    # Check keyword patterns
    scores: dict[str, int] = {}
    for category, patterns in KEYWORD_PATTERNS.items():
        for pattern in patterns:
            if pattern in msg_lower:
                scores[category] = scores.get(category, 0) + 1

    if scores:
        # Return the category with the highest score
        best = max(scores, key=scores.get)  # type: ignore
        if scores[best] >= 1:
            logger.info(f"Quick classify: '{message[:50]}' → {best} (score: {scores[best]})")
            return best

    return None


async def classify_intent(message: str) -> str:
    """
    Classify user intent using keyword matching first, then LLM fallback.
    Returns one of: chat, browser, filesystem, pc_control, system_info, interrupt
    """
    # Try fast keyword classification first
    quick = quick_classify(message)
    if quick:
        return quick

    # Fall back to LLM classification
    try:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message)
        response = await chat_complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Low temperature for consistent classification
        )

        # Parse the response — should be just the category name
        category = response.strip().lower().strip('"').strip("'")

        valid_categories = {"chat", "browser", "filesystem", "pc_control", "system_info"}
        if category in valid_categories:
            logger.info(f"LLM classify: '{message[:50]}' → {category}")
            return category
        else:
            logger.warning(f"LLM returned unknown category: '{category}', defaulting to chat")
            return "chat"

    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        return "chat"  # Default to chat on error


# Tool descriptions for the planner
TOOL_DESCRIPTIONS: dict[str, str] = {
    "browser": """
Available browser tools:
- launch_browser(): Launch Chromium browser
- search_web(query, engine): Search Google/Bing/DuckDuckGo. Args: query (str), engine (str, default "google")
- open_url(url): Open a URL in the browser. Args: url (str)
- get_page_content(): Get title and visible text of the current page
- get_search_results(): Get structured search results
- click_link(text): Click a link by its text. Args: text (str)
- close_browser(): Close the browser
""",
    "filesystem": """
Available filesystem tools:
- list_folders(path): List contents of a directory. Args: path (str)
- search_files(path, pattern): Search for files matching a glob pattern. Args: path (str), pattern (str)
- read_text_file(path): Read a text file. Args: path (str)
- read_pdf(path): Read text from a PDF. Args: path (str)
- create_folder(path): Create a new folder. Args: path (str) [REQUIRES CONFIRMATION]
- copy_file(source, destination): Copy a file. Args: source (str), destination (str) [REQUIRES CONFIRMATION]
- move_file(source, destination): Move a file. Args: source (str), destination (str) [REQUIRES CONFIRMATION]
- rename_file(path, new_name): Rename a file. Args: path (str), new_name (str) [REQUIRES CONFIRMATION]
- delete_file(path): Delete a file. Args: path (str) [DANGEROUS - REQUIRES CONFIRMATION]
""",
    "pc_control": """
Available PC control tools:
- open_application(name): Open an app by name. Args: name (str)
- open_file_or_folder(path): Open a file/folder with default handler. Args: path (str) [REQUIRES CONFIRMATION]
- take_screenshot(save_path): Take a screenshot. Args: save_path (str, optional) [REQUIRES CONFIRMATION]
- type_text(text): Type text into active window. Args: text (str) [REQUIRES CONFIRMATION]
- press_keys(keys): Press keyboard shortcut. Args: keys (list[str]) [REQUIRES CONFIRMATION]
""",
    "system_info": """
Available system info tools:
- get_cpu_usage(): Get current CPU usage percentage
- get_ram_usage(): Get current RAM usage
- get_disk_usage(): Get disk usage for all partitions
- get_system_info(): Get comprehensive system information
- get_summary(): Get a human-readable system summary
""",
}
