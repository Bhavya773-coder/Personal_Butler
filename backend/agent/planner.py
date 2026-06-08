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
from agent.ollama_client import chat_complete, chat_stream, check_ollama_status
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
        self.last_search_results: list[dict] = []

    def set_ws_callback(self, callback: Callable):
        """Set the WebSocket broadcast callback."""
        self._ws_callback = callback

    async def _emit(self, event_type: str, data: dict):
        """Emit event to frontend via WebSocket."""
        if self._ws_callback:
            try:
                await self._ws_callback({"type": event_type, **data})
            except Exception as e:
                logger.error(f"WS broadcast callback failed: {e}")

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

        # Log conversation to DB immediately (User)
        await audit_log.log_conversation(self.session_id, "user", message)

        async for token in chat_stream(messages):
            if self._interrupted:
                full_response += " [interrupted]"
                break
            full_response += token
            await self._emit("llm_token", {"token": token})

        # Log conversation to DB (Assistant)
        await audit_log.log_conversation(self.session_id, "assistant", full_response)
        await self._emit("final", {"response": full_response})
        return full_response

    async def _handle_tool_task(self, message: str, intent: str) -> str:
        """Handle a tool-based task."""
        try:
            # Execute tools directly based on intent
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
        msg_lower = message.lower().strip()

        if intent == "system_info":
            await self._emit("tool_started", {"tool": "system_info", "message": "Checking system status..."})
            action_id = await audit_log.log_action(self.session_id, "tool", "system_info", details={"message": message})
            
            if "cpu" in msg_lower:
                info = system_info.get_cpu_usage()
                result_str = f"CPU usage is currently at {info['cpu_percent']}% across {info['cpu_count_logical']} logical cores."
            elif "ram" in msg_lower or "memory" in msg_lower:
                info = system_info.get_ram_usage()
                result_str = f"RAM usage is currently at {info['percent']}% ({info['used_gb']} GB used of {info['total_gb']} GB). Available: {info['available_gb']} GB."
            elif "disk" in msg_lower or "space" in msg_lower or "free" in msg_lower:
                info = system_info.get_disk_usage()
                parts_str = []
                for part in info.get("partitions", []):
                    parts_str.append(f"{part['device']} ({part['mountpoint']}): {part['free_gb']} GB free of {part['total_gb']} GB ({part['percent']}% used)")
                result_str = "Disk space:\n" + "\n".join(parts_str)
            else:
                result_str = system_info.get_summary()

            await audit_log.update_action(action_id, status="completed", result=result_str)
            await self._emit("tool_done", {"tool": "system_info", "result": result_str})
            return result_str

        elif intent == "pc_control":
            action_id = await audit_log.log_action(self.session_id, "tool", "pc_control_action", details={"message": message})
            try:
                # Determine if we should open something or take screenshot
                if "screenshot" in msg_lower:
                    await self._emit("permission_required", {
                        "action": "take_screenshot",
                        "description": "Take a screenshot of your screen",
                        "level": "confirm",
                    })
                    approved = await permission_engine.request_permission(
                        "take_screenshot", "Take a screenshot of your screen"
                    )
                    if not approved:
                        res_str = "Screenshot cancelled."
                        await audit_log.update_action(action_id, status="cancelled", result=res_str)
                        return res_str

                    await self._emit("tool_started", {"tool": "take_screenshot", "message": "Taking screenshot..."})
                    result = pc_control.take_screenshot(confirmed=True)
                    await self._emit("tool_done", {"tool": "take_screenshot", "result": str(result)})
                    res_str = f"Screenshot saved to {result.get('path', 'desktop')}." if result.get("success") else result.get("error", "Failed.")
                    await audit_log.update_action(action_id, status="completed", result=res_str)
                    return res_str

                # Try to parse target name for opening
                target_name = ""
                for v in ["open the ", "open ", "launch ", "start ", "run ", "show "]:
                    if v in msg_lower:
                        target_name = msg_lower.split(v, 1)[1].strip().rstrip(".")
                        break
                
                # Check for specific app names in msg_lower directly to be safe
                matched_app = None
                for app in ["notepad", "calculator", "calc", "chrome", "google chrome", "downloads", "desktop", "documents", "vscode", "vs code", "visual studio code"]:
                    if app in msg_lower:
                        matched_app = app
                        break
                
                # If target_name is empty but we matched an app, use the matched app
                if not target_name and matched_app:
                    target_name = matched_app

                if target_name:
                    app_exec_name = target_name
                    target_lower = target_name.lower()
                    if target_lower in ["vs code", "vscode", "visual studio code"]:
                        app_exec_name = "vscode"
                    elif target_lower in ["chrome", "google chrome", "browser"]:
                        app_exec_name = "chrome"
                    elif target_lower in ["downloads", "downloads folder", "my downloads"]:
                        app_exec_name = "downloads"
                    elif target_lower in ["desktop", "desktop folder", "my desktop"]:
                        app_exec_name = "desktop"
                    elif target_lower in ["documents", "documents folder", "my documents"]:
                        app_exec_name = "documents"
                    elif target_lower in ["notepad", "the notepad"]:
                        app_exec_name = "notepad"
                    elif target_lower in ["calculator", "calc"]:
                        app_exec_name = "calculator"

                    # Now verify if app_exec_name is valid (mapped app or folder or local path)
                    from tools.pc_control import APP_MAP
                    is_valid_app = (app_exec_name.lower() in ["notepad", "calculator", "calc", "chrome", "google chrome", "downloads", "desktop", "documents", "vscode", "vs code", "visual studio code"] or 
                                    app_exec_name.lower() in APP_MAP)
                    is_valid_path = Path(target_name).exists()
                    
                    import re
                    url_match = re.search(r'(https?://\S+|www\.\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/?\S*)', message)

                    if is_valid_app or is_valid_path:
                        # Determine if folder or app
                        is_folder = app_exec_name.lower() in ["downloads", "desktop", "documents"] or is_valid_path
                        tool_name = "open_folder" if is_folder else "open_application"
                        disp_name = target_name.capitalize()
                        
                        await self._emit("tool_started", {"tool": tool_name, "message": f"Opening {disp_name}..."})
                        result = await pc_control.open_application(app_exec_name)
                        await self._emit("tool_done", {"tool": tool_name, "result": str(result)})
                        
                        res_str = result.get("message", "Opened.")
                        status = "completed" if result.get("success") else "failed"
                        await audit_log.update_action(action_id, status=status, result=res_str)
                        return res_str

                    elif url_match:
                        # Redirect to URL opening!
                        url = url_match.group()
                        if not url.startswith("http"):
                            url = "https://" + url
                        await self._emit("tool_started", {"tool": "open_url", "message": f"Opening {url}..."})
                        result = await browser.open_url(url)
                        
                        if "error" in result:
                            err_str = result["error"]
                            await self._emit("tool_done", {"tool": "open_url", "result": err_str})
                            await audit_log.update_action(action_id, status="failed", result=err_str)
                            return err_str

                        success_msg = f"Opened {url}."
                        await self._emit("tool_done", {"tool": "open_url", "result": success_msg})
                        await audit_log.update_action(action_id, status="completed", result=success_msg)
                        return success_msg

                    else:
                        # Vague phrase, return clarification
                        clarification = "I did not understand what to open. Do you mean an app, a file, or a website?"
                        await audit_log.update_action(action_id, status="failed", result=clarification)
                        return clarification
                else:
                    return await self._handle_chat(message)
            except Exception as pe:
                await audit_log.update_action(action_id, status="failed", result=str(pe))
                raise pe

        elif intent == "browser":
            action_id = await audit_log.log_action(self.session_id, "tool", "browser_action", details={"message": message})
            try:
                # 0. Open Browser/Chrome
                if "open chrome" in msg_lower or "open browser" in msg_lower:
                    await self._emit("tool_started", {"tool": "open_application", "message": "Opening Chrome..."})
                    result = await pc_control.open_application("chrome")
                    await self._emit("tool_done", {"tool": "open_application", "result": str(result)})
                    res_str = result.get("message", "Opened Chrome.")
                    status = "completed" if result.get("success") else "failed"
                    await audit_log.update_action(action_id, status=status, result=res_str)
                    return res_str

                # 1. Search Google/Chrome
                elif "search" in msg_lower:
                    query = self._extract_search_query(message)
                    if not query:
                        res_str = "What would you like me to search for?"
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    engine = "google"
                    if "duckduckgo" in msg_lower or "ddg" in msg_lower:
                        engine = "duckduckgo"
                    elif "bing" in msg_lower:
                        engine = "bing"

                    await self._emit("tool_started", {"tool": "web_search", "message": f"Searching for: {query}"})
                    result = await search.web_search(query, engine=engine)
                    
                    if self._interrupted:
                        await audit_log.update_action(action_id, status="interrupted", result="Interrupted")
                        return "Stopped."

                    if "error" in result:
                        await self._emit("tool_done", {"tool": "web_search", "result": result["error"]})
                        await audit_log.update_action(action_id, status="failed", result=result["error"])
                        return result["error"]

                    self.last_search_results = result.get("results", [])
                    summary_res = result.get("summary", "Search complete.")
                    await self._emit("tool_done", {"tool": "web_search", "result": summary_res})
                    
                    response_str = f"Opened browser search. Here is what I found:\n{summary_res}"
                    await audit_log.update_action(action_id, status="completed", result=response_str)
                    return response_str

                # 2. Open first result
                elif "first result" in msg_lower or "open first result" in msg_lower or "open the first result" in msg_lower:
                    if not self.last_search_results:
                        res_str = "I don't have any search results cached. Please search for something first."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    first_url = self.last_search_results[0]["url"]
                    await self._emit("tool_started", {"tool": "open_url", "message": f"Opening first result: {first_url}"})
                    result = await browser.open_url(first_url)
                    
                    if "error" in result:
                        await self._emit("tool_done", {"tool": "open_url", "result": result["error"]})
                        await audit_log.update_action(action_id, status="failed", result=result["error"])
                        return result["error"]

                    await self._emit("tool_done", {"tool": "open_url", "result": f"Opened {first_url}"})
                    response_str = f"Opened browser search. Opened first result: {first_url}"
                    await audit_log.update_action(action_id, status="completed", result=response_str)
                    return response_str

                # 3. Summarize page
                elif "summarize" in msg_lower:
                    await self._emit("tool_started", {"tool": "get_page_content", "message": "Extracting page content to summarize..."})
                    page_info = await browser.get_page_content()
                    
                    if "error" in page_info:
                        await self._emit("tool_done", {"tool": "get_page_content", "result": page_info["error"]})
                        await audit_log.update_action(action_id, status="failed", result=page_info["error"])
                        return page_info["error"]

                    await self._emit("tool_done", {"tool": "get_page_content", "result": "Content extracted."})
                    
                    content_text = page_info.get("content", "").strip()
                    title = page_info.get("title", "this page")
                    if not content_text:
                        res_str = f"The page '{title}' has no readable text content to summarize."
                        await audit_log.update_action(action_id, status="completed", result=res_str)
                        return res_str

                    status = await check_ollama_status()
                    if status["running"] and status["model_available"]:
                        await self._emit("tool_started", {"tool": "summarize_page", "message": "Summarizing webpage content..."})
                        summary = await self._summarize(f"Summarize the webpage: '{title}'", content_text)
                        await self._emit("tool_done", {"tool": "summarize_page", "result": "Summary complete."})
                        response_str = f"Summary of {title}:\n{summary}"
                    else:
                        preview = content_text[:300] + "..." if len(content_text) > 300 else content_text
                        response_str = f"Ollama is unavailable. Here is a preview of the page '{title}':\n\n{preview}"
                    
                    await audit_log.update_action(action_id, status="completed", result=response_str)
                    return response_str

                # 4. Open website URL
                elif "open " in msg_lower or "go to" in msg_lower or "navigate to" in msg_lower:
                    import re
                    url_match = re.search(r'(https?://\S+|www\.\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/?\S*)', message)
                    if url_match:
                        url = url_match.group()
                        if not url.startswith("http"):
                            url = "https://" + url
                        await self._emit("tool_started", {"tool": "open_url", "message": f"Opening {url}..."})
                        result = await browser.open_url(url)
                        
                        if "error" in result:
                            await self._emit("tool_done", {"tool": "open_url", "result": result["error"]})
                            await audit_log.update_action(action_id, status="failed", result=result["error"])
                            return result["error"]

                        await self._emit("tool_done", {"tool": "open_url", "result": f"Opened {url}"})
                        response_str = f"Opened browser search. Opened {url}."
                        await audit_log.update_action(action_id, status="completed", result=response_str)
                        return response_str
                    else:
                        res_str = "I did not understand what to open. Do you mean an app, a file, or a website?"
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str
                else:
                    return await self._handle_chat(message)
            except Exception as be:
                await audit_log.update_action(action_id, status="failed", result=str(be))
                raise be

        elif intent == "filesystem":
            action_id = await audit_log.log_action(self.session_id, "tool", "filesystem_action", details={"message": message})
            try:
                # 1. Create Folder
                if "create" in msg_lower and "folder" in msg_lower:
                    folder_info = self._extract_folder_info(message)
                    path = folder_info.get("path", "")

                    if not path:
                        res_str = "Where should I create the folder? Please specify a name or path."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    # Safe path validation
                    target_path = Path(path).resolve()
                    if target_path.drive and target_path == Path(target_path.drive).resolve():
                        res_str = "Modifying the root directory of a drive is blocked for safety."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    # Request permission
                    await self._emit("permission_required", {
                        "action": "create_folder",
                        "description": f"Create folder: {path}",
                        "level": "confirm",
                        "details": {"path": path}
                    })
                    approved = await permission_engine.request_permission(
                        "create_folder", f"Create folder: {path}", {"path": path}
                    )

                    if not approved:
                        res_str = "Folder creation cancelled."
                        await audit_log.update_action(action_id, status="cancelled", result=res_str)
                        return res_str

                    await self._emit("tool_started", {"tool": "create_folder", "message": f"Creating folder: {path}"})
                    result = filesystem.create_folder(path)
                    await self._emit("tool_done", {"tool": "create_folder", "result": str(result)})

                    if result.get("success"):
                        response_str = f"Created folder: {result['path']}"
                        await audit_log.update_action(action_id, status="completed", result=response_str)
                        return response_str
                    else:
                        err_str = result.get("error", "Failed to create folder.")
                        await audit_log.update_action(action_id, status="failed", result=err_str)
                        return err_str

                # 2. Search Files (Find files named X or Search Downloads for PDF files)
                elif ("search" in msg_lower or "find" in msg_lower) and ("file" in msg_lower or "pdf" in msg_lower or "document" in msg_lower or "invoice" in msg_lower):
                    search_info = self._extract_file_search(message)
                    search_path = search_info["path"]
                    pattern = search_info["pattern"]

                    target_path = Path(search_path).resolve()
                    if target_path.drive and target_path == Path(target_path.drive).resolve():
                        res_str = "Searching the root directory of a drive is blocked for safety."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    await self._emit("tool_started", {"tool": "search_files", "message": f"Searching {search_path} for {pattern}..."})
                    result = filesystem.search_files(search_path, pattern)
                    await self._emit("tool_done", {"tool": "search_files", "result": f"{result.get('count', 0)} files found"})

                    if result.get("error"):
                        await audit_log.update_action(action_id, status="failed", result=result["error"])
                        return result["error"]

                    count = result.get("count", 0)
                    if count == 0:
                        if "pdf" in msg_lower or ".pdf" in pattern.lower():
                            response_str = "No PDFs found."
                        else:
                            response_str = "No matching files found."
                        await audit_log.update_action(action_id, status="completed", result=response_str)
                        return response_str

                    file_list = "\n".join([f"  • {r['name']} ({r.get('size', 0)} bytes)" for r in result.get("results", [])[:20]])
                    response_str = f"Found {count} file(s) matching '{pattern}' in {search_path}:\n{file_list}"
                    await audit_log.update_action(action_id, status="completed", result=response_str)
                    return response_str

                # 3. List Files
                elif "list" in msg_lower or "show" in msg_lower:
                    path = self._extract_path(message)
                    if not path:
                        if "download" in msg_lower:
                            path = str(Path.home() / "Downloads")
                        elif "document" in msg_lower:
                            path = str(Path.home() / "Documents")
                        else:
                            path = str(Path.home() / "Desktop")

                    target_path = Path(path).resolve()
                    if target_path.drive and target_path == Path(target_path.drive).resolve():
                        res_str = "Listing the root directory of a drive is blocked for safety."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    await self._emit("tool_started", {"tool": "list_folders", "message": f"Listing {path}..."})
                    result = filesystem.list_folders(path)
                    await self._emit("tool_done", {"tool": "list_folders", "result": f"{result.get('count', 0)} items"})

                    if result.get("error"):
                        await audit_log.update_action(action_id, status="failed", result=result["error"])
                        return result["error"]

                    items = result.get("items", [])
                    listing = "\n".join([f"  {'📁' if i['is_dir'] else '📄'} {i['name']}" for i in items[:30]])
                    response_str = f"Contents of {path} ({result['count']} items):\n{listing}"
                    await audit_log.update_action(action_id, status="completed", result=response_str)
                    return response_str

                # 4. Read File
                elif "read" in msg_lower:
                    path = self._extract_path(message)
                    if not path:
                        res_str = "Which file should I read? Please specify a path."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    target_path = Path(path).resolve()
                    if target_path.drive and target_path == Path(target_path.drive).resolve():
                        res_str = "Reading the root directory of a drive is blocked for safety."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    await self._emit("tool_started", {"tool": "read_text_file", "message": f"Reading {path}..."})
                    if path.lower().endswith(".pdf"):
                        result = filesystem.read_pdf(path)
                    else:
                        result = filesystem.read_text_file(path)
                    await self._emit("tool_done", {"tool": "read_file", "result": "File read complete."})

                    if result.get("error"):
                        await audit_log.update_action(action_id, status="failed", result=result["error"])
                        return result["error"]

                    content = result.get("content", "")
                    if not content and "pages" in result:
                        content = "\n\n".join([p["text"] for p in result["pages"]])

                    response_str = f"Contents of {path}:\n{content[:3000]}"
                    await audit_log.update_action(action_id, status="completed", result=response_str)
                    return response_str

                # 5. Delete File
                elif "delete" in msg_lower or "remove" in msg_lower:
                    path = self._extract_path(message)
                    if not path:
                        res_str = "Which file or folder should I delete? Please specify a path."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    target_path = Path(path).resolve()
                    if target_path.drive and target_path == Path(target_path.drive).resolve():
                        res_str = "Modifying the root directory of a drive is blocked for safety."
                        await audit_log.update_action(action_id, status="failed", result=res_str)
                        return res_str

                    # Request permission (Dangerous level!)
                    await self._emit("permission_required", {
                        "action": "delete_file",
                        "description": f"Delete file or folder: {path}",
                        "level": "dangerous",
                        "details": {"path": path}
                    })
                    approved = await permission_engine.request_permission(
                        "delete_file", f"Delete file or folder: {path}", {"path": path}
                    )

                    if not approved:
                        res_str = "Deletion cancelled."
                        await audit_log.update_action(action_id, status="cancelled", result=res_str)
                        return res_str

                    await self._emit("tool_started", {"tool": "delete_file", "message": f"Deleting: {path}"})
                    result = filesystem.delete_file(path, confirmed=True)
                    await self._emit("tool_done", {"tool": "delete_file", "result": str(result)})

                    if result.get("success"):
                        response_str = f"Successfully deleted: {path}"
                        await audit_log.update_action(action_id, status="completed", result=response_str)
                        return response_str
                    else:
                        err_str = result.get("error", "Failed to delete.")
                        await audit_log.update_action(action_id, status="failed", result=err_str)
                        return err_str
                else:
                    return await self._handle_chat(message)
            except Exception as fe:
                await audit_log.update_action(action_id, status="failed", result=str(fe))
                raise fe

        return await self._handle_chat(message)

    def _extract_search_query(self, message: str) -> str:
        """Extract the search query from a user message."""
        msg_lower = message.lower().strip()

        prefixes = [
            "search chrome for ", "search google for ", "search for ",
            "search the web for ", "search bing for ", "search duckduckgo for ",
            "google ", "search ", "look up ", "find information about ",
            "search chrome ", "web search ",
        ]
        for prefix in prefixes:
            if msg_lower.startswith(prefix):
                return message[len(prefix):].strip().rstrip(".")

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

        desktop = str(Path.home() / "Desktop")
        downloads = str(Path.home() / "Downloads")
        documents = str(Path.home() / "Documents")

        # Determine base path
        base_path = desktop
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
                for loc in [" on desktop", " on the desktop", " on downloads", " in documents"]:
                    if name.lower().endswith(loc):
                        name = name[:-len(loc)]
                break

        if not name:
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

        # 1. Determine search path
        home = Path.home()
        if "download" in msg_lower:
            search_path = str(home / "Downloads")
        elif "desktop" in msg_lower:
            search_path = str(home / "Desktop")
        elif "document" in msg_lower:
            search_path = str(home / "Documents")
        else:
            extracted_path = self._extract_path(message)
            search_path = extracted_path or str(home / "Downloads")

        # 2. Determine pattern
        pattern = "*"
        if "pdf" in msg_lower:
            pattern = "*.pdf"
        elif "txt" in msg_lower or "text" in msg_lower:
            pattern = "*.txt"
        elif "md" in msg_lower or "markdown" in msg_lower:
            pattern = "*.md"
        elif "doc" in msg_lower or "docx" in msg_lower:
            pattern = "*.docx"

        # Check for keyword (e.g. named invoice)
        import re
        match = re.search(r'(?:named|called)\s+(\w+)', message, re.IGNORECASE)
        if match:
            keyword = match.group(1).strip()
            if pattern != "*":
                ext = pattern.split(".")[-1]
                pattern = f"*{keyword}*.{ext}"
            else:
                pattern = f"*{keyword}*"
        elif "named " in msg_lower:
            idx = msg_lower.index("named ") + len("named ")
            keyword = message[idx:].strip().rstrip(".").strip('"').strip("'")
            if pattern != "*":
                ext = pattern.split(".")[-1]
                pattern = f"*{keyword}*.{ext}"
            else:
                pattern = f"*{keyword}*"

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

        # Check for standard extension keyword if no path matched (e.g. invoice.txt on Desktop)
        match = re.search(r'([a-zA-Z0-9_-]+\.[a-zA-Z0-9]{2,4})', message)
        if match:
            filename = match.group(1)
            if "desktop" in message.lower():
                return str(Path.home() / "Desktop" / filename)
            elif "download" in message.lower():
                return str(Path.home() / "Downloads" / filename)
            elif "document" in message.lower():
                return str(Path.home() / "Documents" / filename)
            else:
                return str(Path.home() / "Desktop" / filename)

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
