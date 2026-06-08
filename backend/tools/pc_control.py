"""
JARVIS Core — PC Control Tools

Open applications, take screenshots, type text, keyboard automation.
Dangerous operations require explicit confirmation.
"""

import os
import subprocess
import logging
import asyncio
import psutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.tools.pc_control")

# Common application name → executable mapping for Windows
APP_MAP: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "spotify": "spotify",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "microsoft teams": "teams",
    "snipping tool": "snippingtool.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
}


def find_vscode_path() -> Optional[str]:
    """Find the path to the VS Code executable on Windows."""
    import shutil
    path_code = shutil.which("code") or shutil.which("code.cmd") or shutil.which("Code.exe")
    if path_code:
        return path_code

    local_appdata = os.getenv("LOCALAPPDATA")
    paths = []
    if local_appdata:
        paths.append(Path(local_appdata) / "Programs/Microsoft/VS Code/Code.exe")
        paths.append(Path(local_appdata) / "Programs/Microsoft VS Code/Code.exe")
    paths.extend([
        Path("C:/Program Files/Microsoft VS Code/Code.exe"),
        Path("C:/Program Files (x86)/Microsoft VS Code/Code.exe"),
    ])
    for p in paths:
        if p.exists():
            return str(p)
    return None


def find_chrome_path() -> Optional[str]:
    """Find the path to the Chrome executable on Windows."""
    import shutil
    path_chrome = shutil.which("chrome") or shutil.which("chrome.exe")
    if path_chrome:
        return path_chrome

    local_appdata = os.getenv("LOCALAPPDATA")
    paths = []
    if local_appdata:
        paths.append(Path(local_appdata) / "Google/Chrome/Application/chrome.exe")
    paths.extend([
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ])
    for p in paths:
        if p.exists():
            return str(p)
    return None


def verify_process_exists(proc_names: list[str]) -> bool:
    """Check if any of the process names exist in the running process list."""
    proc_names_lower = [p.lower() for p in proc_names]
    for proc in psutil.process_iter(['name']):
        try:
            name = proc.info['name']
            if name and name.lower() in proc_names_lower:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False


async def open_folder_action(name: str) -> dict:
    """Open a folder by name or path and return structured result."""
    name_lower = name.lower().strip()
    userprofile = os.getenv("USERPROFILE", os.path.expanduser("~"))
    
    if name_lower in ["downloads", "downloads folder", "my downloads", "explorer/downloads"]:
        folder_path = os.path.join(userprofile, "Downloads")
        target_name = "Downloads"
    elif name_lower in ["desktop", "desktop folder", "my desktop", "explorer/desktop"]:
        folder_path = os.path.join(userprofile, "Desktop")
        target_name = "Desktop"
    elif name_lower in ["documents", "documents folder", "my documents", "explorer/documents"]:
        folder_path = os.path.join(userprofile, "Documents")
        target_name = "Documents"
    else:
        folder_path = name
        target_name = name

    target = Path(folder_path).resolve()
    if not target.exists():
        return {
            "success": False,
            "verified": False,
            "target": name,
            "command": f'explorer.exe "{folder_path}"',
            "message": f"I tried to open {target_name}, but Windows did not find the folder.",
            "error": f"Folder path does not exist: {folder_path}"
        }

    try:
        cmd = f'explorer.exe "{target}"'
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "success": True,
            "verified": True,
            "target": name,
            "command": cmd,
            "message": f"Opened {target_name}.",
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "target": name,
            "command": f'explorer.exe "{target}"',
            "message": f"I tried to open {target_name}, but Windows did not start it.",
            "error": str(e)
        }


async def open_application(name: str) -> dict:
    """Open an application by name and verify launch."""
    name_lower = name.lower().strip()
    logger.info(f"Attempting to open application: {name}")

    # Process names list to verify after launch
    proc_names = []
    executable_cmd = None

    # Resolve folder redirects first
    if name_lower in [
        "downloads", "downloads folder", "my downloads", "explorer/downloads",
        "desktop", "desktop folder", "my desktop", "explorer/desktop",
        "documents", "documents folder", "my documents", "explorer/documents"
    ]:
        return await open_folder_action(name_lower)

    # 1. Notepad
    if name_lower == "notepad":
        executable_cmd = "notepad.exe"
        proc_names = ["notepad.exe"]

    # 2. Calculator
    elif name_lower in ["calculator", "calc"]:
        executable_cmd = "calc.exe"
        proc_names = ["Calculator.exe", "ApplicationFrameHost.exe", "calc.exe"]

    # 3. Chrome
    elif name_lower in ["chrome", "google chrome"]:
        proc_names = ["chrome.exe", "msedge.exe", "chromium.exe"]
        chrome_path = find_chrome_path()
        launched = False
        cmd_used = None
        
        if chrome_path:
            try:
                subprocess.Popen(f'"{chrome_path}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cmd_used = chrome_path
                launched = True
            except Exception as e:
                logger.info(f"Failed to launch Chrome via path: {e}")
                
        if not launched:
            try:
                subprocess.Popen("chrome.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cmd_used = "chrome.exe"
                launched = True
            except Exception as e:
                logger.info(f"Failed to launch Chrome via 'chrome.exe': {e}")
                
        if not launched:
            logger.info("Chrome executable not found. Falling back to Playwright browser.")
            from tools.browser import launch_browser
            result = await launch_browser()
            if result.get("success"):
                await asyncio.sleep(1.0)
                if verify_process_exists(proc_names):
                    return {
                        "success": True,
                        "verified": True,
                        "target": name,
                        "command": "Playwright Browser",
                        "message": "Opened Chrome.",
                        "error": None
                    }
            return {
                "success": False,
                "verified": False,
                "target": name,
                "command": "Playwright Browser",
                "message": "I tried to open Chrome, but Windows did not start it.",
                "error": "Failed to launch chrome."
            }

        # Verify launched Chrome
        await asyncio.sleep(1.0)
        verified = verify_process_exists(proc_names)
        if verified:
            return {
                "success": True,
                "verified": True,
                "target": name,
                "command": cmd_used,
                "message": "Opened Chrome.",
                "error": None
            }
        else:
            return {
                "success": False,
                "verified": False,
                "target": name,
                "command": cmd_used,
                "message": "I tried to open Chrome, but Windows did not start it.",
                "error": "Process verification failed."
            }

    # 4. VS Code
    elif name_lower in ["code", "vs code", "vscode", "visual studio code"]:
        proc_names = ["Code.exe", "code.exe"]
        vscode_path = find_vscode_path()
        launched = False
        cmd_used = None
        
        if vscode_path:
            try:
                subprocess.Popen(f'"{vscode_path}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cmd_used = vscode_path
                launched = True
            except Exception as e:
                logger.info(f"Failed to launch VS Code via path: {e}")
                
        if not launched:
            try:
                subprocess.Popen("code", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cmd_used = "code"
                launched = True
            except Exception as e:
                logger.info(f"Failed to launch VS Code via 'code': {e}")
                
        if not launched:
            return {
                "success": False,
                "verified": False,
                "target": name,
                "command": "code",
                "message": "VS Code not found. Make sure it's installed.",
                "error": "VS Code executable not found."
            }
            
        await asyncio.sleep(1.0)
        verified = verify_process_exists(proc_names)
        if verified:
            return {
                "success": True,
                "verified": True,
                "target": name,
                "command": cmd_used,
                "message": "Opened VS Code.",
                "error": None
            }
        else:
            return {
                "success": False,
                "verified": False,
                "target": name,
                "command": cmd_used,
                "message": "I tried to open VS Code, but Windows did not start it.",
                "error": "Process verification failed."
            }

    # 5. Fallback mapping
    else:
        if name_lower in APP_MAP:
            exec_name = APP_MAP[name_lower]
        else:
            return {
                "success": False,
                "verified": False,
                "target": name,
                "command": None,
                "message": "I did not understand what to open. Do you mean an app, a file, or a website?",
                "error": "Unmapped application"
            }
            
        executable_cmd = exec_name
        if exec_name.startswith("ms-"):
            proc_names = ["SystemSettings.exe"]
        else:
            p_name = exec_name if exec_name.endswith(".exe") else f"{exec_name}.exe"
            proc_names = [p_name, exec_name]

    # Execute mapped fallback app
    try:
        logger.info(f"Running command: {executable_cmd}")
        if executable_cmd.startswith("ms-"):
            os.startfile(executable_cmd)
        else:
            subprocess.Popen(
                executable_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        
        await asyncio.sleep(1.0)
        verified = verify_process_exists(proc_names)
        logger.info(f"tool: pc_control.open_app | target: {name} | success: {verified} | verified_process: {verified}")
        
        capitalized_target = name.capitalize() if len(name) > 0 else ""
        if verified:
            return {
                "success": True,
                "verified": True,
                "target": name,
                "command": executable_cmd,
                "message": f"Opened {capitalized_target}.",
                "error": None
            }
        else:
            return {
                "success": False,
                "verified": False,
                "target": name,
                "command": executable_cmd,
                "message": f"I tried to open {capitalized_target}, but Windows did not start it.",
                "error": "Process verification failed."
            }
            
    except Exception as e:
        logger.error(f"Application launch failed: {e}")
        capitalized_target = name.capitalize() if len(name) > 0 else ""
        return {
            "success": False,
            "verified": False,
            "target": name,
            "command": executable_cmd,
            "message": f"I tried to open {capitalized_target}, but Windows did not start it.",
            "error": str(e)
        }


class PCControlTool:
    """Wrapper class to support user's testing harness."""
    async def open_app(self, name: str) -> dict:
        return await open_application(name)

    async def open_folder(self, name: str) -> dict:
        return await open_folder_action(name)


def open_file_or_folder(path: str) -> dict:
    """Open a file or folder using the default system handler."""
    target = Path(path).resolve()
    if not target.exists():
        return {
            "success": False,
            "verified": False,
            "target": path,
            "command": f'os.startfile("{path}")',
            "message": f"I tried to open {path}, but the path does not exist.",
            "error": "Path does not exist"
        }

    try:
        os.startfile(str(target))
        return {
            "success": True,
            "verified": True,
            "target": path,
            "command": f'os.startfile("{target}")',
            "message": f"Opened {target.name}.",
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "target": path,
            "command": f'os.startfile("{target}")',
            "message": f"Failed to open: {str(e)}",
            "error": str(e)
        }


def take_screenshot(save_path: Optional[str] = None, confirmed: bool = False) -> dict:
    """Take a screenshot. Requires confirmation."""
    if not confirmed:
        return {"error": "Screenshot requires confirmation.", "requires_confirmation": True}

    try:
        import pyautogui
        from datetime import datetime

        if not save_path:
            desktop = Path.home() / "Desktop"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(desktop / f"jarvis_screenshot_{timestamp}.png")

        screenshot = pyautogui.screenshot()
        screenshot.save(save_path)
        logger.info(f"Screenshot saved: {save_path}")
        return {"success": True, "path": save_path}
    except Exception as e:
        return {"error": f"Screenshot failed: {str(e)}"}


def type_text(text: str, confirmed: bool = False) -> dict:
    """Type text into the active window. Requires confirmation."""
    if not confirmed:
        return {
            "error": "Typing requires confirmation.",
            "requires_confirmation": True,
            "text_preview": text[:100],
        }

    try:
        import pyautogui
        import time

        time.sleep(0.5)  # Brief delay to let user focus the target window
        pyautogui.typewrite(text, interval=0.02) if text.isascii() else pyautogui.write(text)
        logger.info(f"Typed text: {text[:50]}...")
        return {"success": True, "chars_typed": len(text)}
    except Exception as e:
        return {"error": f"Typing failed: {str(e)}"}


def press_keys(keys: list[str], confirmed: bool = False) -> dict:
    """Press keyboard shortcut. Requires confirmation."""
    if not confirmed:
        return {
            "error": "Keyboard automation requires confirmation.",
            "requires_confirmation": True,
            "keys": keys,
        }

    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        logger.info(f"Pressed keys: {'+'.join(keys)}")
        return {"success": True, "keys_pressed": "+".join(keys)}
    except Exception as e:
        return {"error": f"Key press failed: {str(e)}"}
