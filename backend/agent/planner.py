"""
JARVIS Core — Task Planner

Creates action plans from user intent and executes tools.
Manages the flow: classify → plan → permission check → execute → summarize.
"""

import json
import logging
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

from agent.router import classify_intent, TOOL_DESCRIPTIONS
from agent.ollama_client import chat_complete, chat_stream
from agent.prompts import (
    JARVIS_SYSTEM_PROMPT,
    TASK_PLANNING_PROMPT,
    SUMMARIZE_RESULTS_PROMPT,
)
from agent.memory import memory
from security.permissions import permission_engine, PermissionLevel
from security.audit_log import audit_log
from tools import system_info, filesystem, pc_control, browser, search

logger = logging.getLogger("jarvis.agent.planner")


class TaskPlanner:
    """Orchestrates task planning and execution."""

    def __init__(self):
        self.session_id = "default"
        self._interrupted = False
        self._ws_callback: Optional[Callable] = None

    def set_ws_callback(self, callback: Callable):
        """Set the WebSocket broadcast callback."""
        self._ws_callback = callback

    async def _emit(self, event_type: str, data: dict):
        """Emit event to frontend via WebSocket."""
        if self._ws_callback:
            await self._ws_callback({"type": event_type, **data})

    def interrupt(self):
        """Set the interrupt flag."""
        self._interrupted = True

    def reset_interrupt(self):
        """Clear the interrupt flag."""
        self._interrupted = False

    async def handle_message(self, message: str) -> str:
        """
        Main entry point for processing a user message.
        Returns the final response text.
        """
        self.reset_interrupt()
        memory.add_message("user", message)

        # 1. Classify intent
        await self._emit("tool_started", {"tool": "intent_classification", "message": "Understanding your request..."})
        intent = await classify_intent(message)
        logger.info(f"Intent: {intent} for message: '{message[:60]}'")

        if self._interrupted:
            return "Stopped."

        # 2. Route based on intent
        if intent == "interrupt":
            return "Stopped."
        elif intent == "chat":
            return await self._handle_chat(message)
        else:
            return await self._handle_tool_task(message, intent)

    async def _handle_chat(self, message: str) -> str:
        """Handle a chat/conversation message by streaming from Ollama."""
        messages = memory.get_messages_for_llm(JARVIS_SYSTEM_PROMPT)
        full_response = ""

        async for token in chat_stream(messages):
            if self._interrupted:
                full_response += " [interrupted]"
                break
            full_response += token
            await self._emit("llm_token", {"token": token})

        memory.add_message("assistant", full_response)
        await audit_log.log_conversation(self.session_id, "user", message)
        await audit_log.log_conversation(self.session_id, "assistant", full_response)
        await self._emit("final", {"response": full_response})
        return full_response

    async def _handle_tool_task(self, message: str, intent: str) -> str:
        """Handle a tool-based task."""
        try:
            # Execute tools directly based on intent (simpler and more reliable than LLM planning)
            result = await self._execute_direct(message, intent)

            if self._interrupted:
                return "Stopped."

            # Summarize results using LLM
            if result:
                summary = await self._summarize(message, result)
                memory.add_message("assistant", summary)
                await audit_log.log_conversation(self.session_id, "user", message)
                await audit_log.log_conversation(self.session_id, "assistant", summary)
                await self._emit("final", {"response": summary})
                return summary
            else:
                fallback = "I tried but couldn't complete that task. Could you rephrase?"
                await self._emit("final", {"response": fallback})
                return fallback

        except Exception as e:
            error_msg = f"Something went wrong: {str(e)}"
            logger.error(f"Tool task error: {traceback.format_exc()}")
            await audit_log.log_error(self.session_id, "tool_task", str(e), traceback.format_exc())
            await self._emit("error", {"message": error_msg})
            return error_msg

    async def _execute_direct(self, message: str, intent: str) -> str:
        """Execute tools directly based on keyword matching in the message."""
        msg_lower = message.lower()
        results = []

        if intent == "system_info":
            await self._emit("tool_started", {"tool": "system_info", "message": "Checking system status..."})
            summary = system_info.get_summary()
            action_id = await audit_log.log_action(self.session_id, "tool", "system_info", status="completed", result=summary)
            await self._emit("tool_done", {"tool": "system_info", "result": summary})
            return summary

        elif intent == "pc_control":
            # Determine which PC action
            if any(w in msg_lower for w in ["open notepad", "launch notepad"]):
                await self._emit("tool_started", {"tool": "open_application", "message": "Opening Notepad..."})
                result = pc_control.open_application("notepad")
                await self._emit("tool_done", {"tool": "open_application", "result": str(result)})
                return f"Opened Notepad." if result.get("success") else result.get("error", "Failed to open.")

            elif any(w in msg_lower for w in ["open chrome", "launch chrome"]):
                await self._emit("tool_started", {"tool": "launch_browser", "message": "Opening Chrome..."})
                result = await browser.launch_browser()
                await self._emit("tool_done", {"tool": "launch_browser", "result": str(result)})
                return "Chrome is open." if result.get("success") else result.get("error", "Failed to open browser.")

            elif "open " in msg_lower:
                # Extract app name after "open"
                app_name = msg_lower.split("open", 1)[1].strip().rstrip(".")
                await self._emit("tool_started", {"tool": "open_application", "message": f"Opening {app_name}..."})
                result = pc_control.open_application(app_name)
                await self._emit("tool_done", {"tool": "open_application", "result": str(result)})
                return f"Opened {app_name}." if result.get("success") else result.get("error", "Failed to open.")

            elif "screenshot" in msg_lower:
                # Request permission
                level = permission_engine.get_level("take_screenshot")
                if level != PermissionLevel.SAFE:
                    await self._emit("permission_required", {
                        "action": "take_screenshot",
                        "description": "Take a screenshot of your screen",
                        "level": level.value,
                    })
                    approved = await permission_engine.request_permission(
                        "take_screenshot", "Take a screenshot of your screen"
                    )
                    if not approved:
                        return "Screenshot cancelled."

                result = pc_control.take_screenshot(confirmed=True)
                return f"Screenshot saved to {result.get('path', 'desktop')}." if result.get("success") else result.get("error", "Failed.")

            else:
                return await self._handle_chat(message)

        elif intent == "browser":
            if "open chrome" in msg_lower or "open browser" in msg_lower:
                await self._emit("tool_started", {"tool": "launch_browser", "message": "Opening browser..."})
                result = await browser.launch_browser()
                await self._emit("tool_done", {"tool": "launch_browser", "result": str(result)})
                return "Browser is open." if result.get("success") else result.get("error", "Failed to open browser.")

            elif "search" in msg_lower:
                # Extract search query
                query = self._extract_search_query(message)
                if not query:
                    return "What would you like me to search for?"

                await self._emit("tool_started", {"tool": "web_search", "message": f"Searching for: {query}"})
                result = await search.web_search(query)

                if self._interrupted:
                    return "Stopped."

                await self._emit("tool_done", {"tool": "web_search", "result": result.get("summary", "Search complete.")})

                if result.get("error"):
                    return result["error"]
                return result.get("summary", "Search completed. Check the browser window for results.")

            elif "open " in msg_lower and ("http" in msg_lower or "www" in msg_lower or ".com" in msg_lower):
                # Extract URL
                import re
                url_match = re.search(r'(https?://\S+|www\.\S+)', message)
                if url_match:
                    url = url_match.group()
                    if not url.startswith("http"):
                        url = "https://" + url
                    await self._emit("tool_started", {"tool": "open_url", "message": f"Opening {url}..."})
                    result = await browser.open_url(url)
                    await self._emit("tool_done", {"tool": "open_url", "result": str(result)})
                    return f"Opened {url}." if result.get("success") else result.get("error", "Failed.")

            else:
                return await self._handle_chat(message)

        elif intent == "filesystem":
            if "create" in msg_lower and "folder" in msg_lower:
                # Extract folder name and path
                folder_info = self._extract_folder_info(message)
                path = folder_info.get("path", "")

                if not path:
                    return "Where should I create the folder? Please specify a name or path."

                # Request permission
                await self._emit("permission_required", {
                    "action": "create_folder",
                    "description": f"Create folder: {path}",
                    "level": "confirm",
                })
                approved = await permission_engine.request_permission(
                    "create_folder", f"Create folder: {path}", {"path": path}
                )

                if not approved:
                    return "Folder creation cancelled."

                await self._emit("tool_started", {"tool": "create_folder", "message": f"Creating folder: {path}"})
                result = filesystem.create_folder(path)
                await self._emit("tool_done", {"tool": "create_folder", "result": str(result)})

                if result.get("success"):
                    return f"Created folder: {result['path']}"
                else:
                    return result.get("error", "Failed to create folder.")

            elif "search" in msg_lower and ("file" in msg_lower or "pdf" in msg_lower or "document" in msg_lower):
                # Extract search location and pattern
                search_info = self._extract_file_search(message)
                search_path = search_info["path"]
                pattern = search_info["pattern"]

                await self._emit("tool_started", {"tool": "search_files", "message": f"Searching {search_path} for {pattern}..."})
                result = filesystem.search_files(search_path, pattern)
                await self._emit("tool_done", {"tool": "search_files", "result": str(result.get("count", 0)) + " files found"})

                if result.get("error"):
                    return result["error"]

                count = result.get("count", 0)
                if count == 0:
                    return f"No files matching '{pattern}' found in {search_path}."

                file_list = "\n".join([f"  • {r['name']} ({r.get('size', 0)} bytes)" for r in result.get("results", [])[:20]])
                return f"Found {count} file(s) matching '{pattern}' in {search_path}:\n{file_list}"

            elif "list" in msg_lower or "show" in msg_lower:
                # Extract path
                path = self._extract_path(message) or str(Path.home() / "Desktop")
                await self._emit("tool_started", {"tool": "list_folders", "message": f"Listing {path}..."})
                result = filesystem.list_folders(path)
                await self._emit("tool_done", {"tool": "list_folders", "result": f"{result.get('count', 0)} items"})

                if result.get("error"):
                    return result["error"]

                items = result.get("items", [])
                listing = "\n".join([f"  {'📁' if i['is_dir'] else '📄'} {i['name']}" for i in items[:30]])
                return f"Contents of {path} ({result['count']} items):\n{listing}"

            elif "read" in msg_lower:
                path = self._extract_path(message)
                if not path:
                    return "Which file should I read? Please provide a path."

                await self._emit("tool_started", {"tool": "read_text_file", "message": f"Reading {path}..."})
                if path.lower().endswith(".pdf"):
                    result = filesystem.read_pdf(path)
                else:
                    result = filesystem.read_text_file(path)
                await self._emit("tool_done", {"tool": "read_file", "result": "File read complete."})

                if result.get("error"):
                    return result["error"]

                content = result.get("content", "")
                if not content and "pages" in result:
                    content = "\n\n".join([p["text"] for p in result["pages"]])

                return f"Contents of {path}:\n{content[:3000]}"

            else:
                return await self._handle_chat(message)

        return await self._handle_chat(message)

    def _extract_search_query(self, message: str) -> str:
        """Extract the search query from a user message."""
        msg_lower = message.lower()

        # Remove common prefixes
        prefixes = [
            "search chrome for ", "search google for ", "search for ",
            "search the web for ", "search bing for ", "search duckduckgo for ",
            "google ", "search ", "look up ", "find information about ",
            "search chrome ", "web search ",
        ]
        for prefix in prefixes:
            if msg_lower.startswith(prefix):
                return message[len(prefix):].strip().rstrip(".")

        # If "search" is in the middle, take everything after it
        if "search for " in msg_lower:
            idx = msg_lower.index("search for ") + len("search for ")
            return message[idx:].strip().rstrip(".")

        if "search " in msg_lower:
            idx = msg_lower.index("search ") + len("search ")
            return message[idx:].strip().rstrip(".")

        return message.strip().rstrip(".")

    def _extract_folder_info(self, message: str) -> dict:
        """Extract folder creation info from message."""
        msg_lower = message.lower()

        # Common patterns: "create a folder on Desktop called X"
        # "create folder named X on Desktop"
        # "make a folder X on the Desktop"
        desktop = str(Path.home() / "Desktop")
        downloads = str(Path.home() / "Downloads")
        documents = str(Path.home() / "Documents")

        # Determine base path
        base_path = desktop  # default
        if "download" in msg_lower:
            base_path = downloads
        elif "document" in msg_lower:
            base_path = documents
        elif "desktop" in msg_lower:
            base_path = desktop

        # Extract folder name
        name = ""
        for pattern_word in ["called ", "named ", "name "]:
            if pattern_word in msg_lower:
                idx = msg_lower.index(pattern_word) + len(pattern_word)
                name = message[idx:].strip().rstrip(".").strip('"').strip("'")
                # Remove trailing location words
                for loc in [" on desktop", " on the desktop", " on downloads", " in documents"]:
                    if name.lower().endswith(loc):
                        name = name[:len(name)-len(loc)]
                break

        if not name:
            # Try to extract from "create folder X"
            import re
            match = re.search(r'(?:create|make)\s+(?:a\s+)?folder\s+(?:on\s+\w+\s+)?(.+?)(?:\s+on\s+|\s*$)', message, re.IGNORECASE)
            if match:
                name = match.group(1).strip().rstrip(".")

        if name:
            full_path = str(Path(base_path) / name)
            return {"path": full_path, "name": name}

        return {"path": "", "name": ""}

    def _extract_file_search(self, message: str) -> dict:
        """Extract file search parameters from message."""
        msg_lower = message.lower()

        # Determine search path
        home = Path.home()
        if "download" in msg_lower:
            search_path = str(home / "Downloads")
        elif "desktop" in msg_lower:
            search_path = str(home / "Desktop")
        elif "document" in msg_lower:
            search_path = str(home / "Documents")
        else:
            search_path = str(home / "Downloads")  # default

        # Determine pattern
        if "pdf" in msg_lower:
            pattern = "*.pdf"
        elif "word" in msg_lower or "docx" in msg_lower:
            pattern = "*.docx"
        elif "excel" in msg_lower or "xlsx" in msg_lower:
            pattern = "*.xlsx"
        elif "image" in msg_lower or "photo" in msg_lower:
            pattern = "*.{png,jpg,jpeg,gif,bmp}"
        elif "video" in msg_lower:
            pattern = "*.{mp4,avi,mkv,mov}"
        elif "text" in msg_lower or "txt" in msg_lower:
            pattern = "*.txt"
        else:
            pattern = "*"

        return {"path": search_path, "pattern": pattern}

    def _extract_path(self, message: str) -> str | None:
        """Extract a file/folder path from a message."""
        import re
        # Match quoted paths
        match = re.search(r'["\'](.+?)["\']', message)
        if match:
            return match.group(1)

        # Match Windows-style paths
        match = re.search(r'([A-Z]:\\[^\s"]+)', message)
        if match:
            return match.group(1)

        # Match relative paths starting with ~/
        match = re.search(r'(~/[^\s"]+)', message)
        if match:
            return str(Path.home() / match.group(1)[2:])

        return None

    async def _summarize(self, request: str, results: str) -> str:
        """Use LLM to create a natural summary if the result is complex."""
        # For short results, just return them directly
        if len(results) < 200:
            return results

        # For longer results, stream a summary through LLM
        prompt = SUMMARIZE_RESULTS_PROMPT.format(request=request, results=results[:3000])
        full_response = ""

        async for token in chat_stream(
            messages=[
                {"role": "system", "content": JARVIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        ):
            if self._interrupted:
                break
            full_response += token
            await self._emit("llm_token", {"token": token})

        return full_response or results


# Singleton
planner = TaskPlanner()
