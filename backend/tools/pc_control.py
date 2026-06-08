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


async def open_application(name: str) -> dict:
    """Open an application by name and verify launch."""
    name_lower = name.lower().strip()
    logger.info(f"Attempting to open application: {name}")

    # Process names list to verify after launch
    proc_names = []
    executable_cmd = None

    if name_lower == "notepad":
        executable_cmd = "notepad.exe"
        proc_names = ["notepad.exe"]
    elif name_lower in ["calculator", "calc"]:
        executable_cmd = "calc.exe"
        proc_names = ["Calculator.exe", "ApplicationFrameHost.exe", "calc.exe"]
    elif name_lower in ["downloads", "downloads folder", "my downloads", "explorer/downloads"]:
        userprofile = os.getenv("USERPROFILE", os.path.expanduser("~"))
        executable_cmd = f'explorer.exe "{os.path.join(userprofile, "Downloads")}"'
        proc_names = ["explorer.exe"]
    elif name_lower in ["desktop", "desktop folder", "my desktop", "explorer/desktop"]:
        userprofile = os.getenv("USERPROFILE", os.path.expanduser("~"))
        executable_cmd = f'explorer.exe "{os.path.join(userprofile, "Desktop")}"'
        proc_names = ["explorer.exe"]
    elif name_lower in ["documents", "documents folder", "my documents", "explorer/documents"]:
        userprofile = os.getenv("USERPROFILE", os.path.expanduser("~"))
        executable_cmd = f'explorer.exe "{os.path.join(userprofile, "Documents")}"'
        proc_names = ["explorer.exe"]
    elif name_lower in ["code", "vs code", "vscode", "visual studio code"]:
        proc_names = ["Code.exe", "code.exe"]
        # Try 'code' command first
        try:
            logger.info("Attempting to open VS Code via 'code' command")
            subprocess.Popen("code", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(1.0)
            if verify_process_exists(proc_names):
                logger.info("VS Code launch verified (code)")
                return {"success": True, "application": name, "executable": "code"}
        except Exception as e:
            logger.info(f"Failed to start VS Code via code command: {e}")

        # Fallback to absolute path
        vscode_path = find_vscode_path()
        if vscode_path:
            executable_cmd = f'"{vscode_path}"'
        else:
            return {"error": "VS Code not found. Make sure it's installed."}
            
    elif name_lower in ["chrome", "google chrome"]:
        proc_names = ["chrome.exe"]
        # Try 'start chrome'
        try:
            logger.info("Attempting to open Chrome via 'start chrome' command")
            subprocess.Popen("start chrome", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(1.0)
            if verify_process_exists(proc_names):
                logger.info("Chrome launch verified (start chrome)")
                return {"success": True, "application": name, "executable": "start chrome"}
        except Exception as e:
            logger.info(f"Failed to start Chrome via start chrome: {e}")

        # Try common paths
        for path in [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ]:
            if Path(path).exists():
                try:
                    logger.info(f"Attempting to open Chrome via path: {path}")
                    subprocess.Popen(f'"{path}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    await asyncio.sleep(1.0)
                    if verify_process_exists(proc_names):
                        logger.info(f"Chrome launch verified ({path})")
                        return {"success": True, "application": name, "executable": path}
                except Exception as e:
                    logger.info(f"Failed to start Chrome via path {path}: {e}")

        # Fallback to Playwright browser
        logger.info("Falling back to Playwright browser launch")
        from tools.browser import launch_browser
        result = await launch_browser()
        if result.get("success"):
            if verify_process_exists(["chrome.exe", "chromium.exe"]):
                logger.info("Chrome/Chromium launch verified via Playwright")
                return {"success": True, "application": name, "executable": "Playwright Browser"}
        return {"error": "I tried to open Chrome, but Windows did not start it."}

    else:
        # Fallback to APP_MAP or raw name
        exec_name = APP_MAP.get(name_lower, name_lower)
        executable_cmd = exec_name
        p_name = exec_name if exec_name.endswith(".exe") else f"{exec_name}.exe"
        proc_names = [p_name, exec_name]

    # Execute and verify
    try:
        logger.info(f"Running command: {executable_cmd}")
        if executable_cmd.startswith("ms-"):
            # Windows URI scheme
            os.startfile(executable_cmd)
        else:
            subprocess.Popen(
                executable_cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        
        # Wait 1 second and verify process launch
        await asyncio.sleep(1.0)
        
        verified = verify_process_exists(proc_names)
        logger.info(f"tool: pc_control.open_app | target: {name} | success: {verified} | verified_process: {verified}")
        
        if verified:
            return {"success": True, "application": name, "executable": executable_cmd}
        else:
            return {"error": f"I tried to open {name.capitalize()}, but Windows did not start it."}
            
    except FileNotFoundError as e:
        logger.error(f"Application launch failed - file not found: {e}")
        return {"error": f"Application not found: {name}. Make sure it's installed."}
    except Exception as e:
        logger.error(f"Application launch failed: {e}")
        return {"error": f"Failed to open {name}: {str(e)}"}


class PCControlTool:
    """Wrapper class to support user's testing harness."""
    async def open_app(self, name: str) -> dict:
        return await open_application(name)


def open_file_or_folder(path: str) -> dict:
    """Open a file or folder using the default system handler."""
    target = Path(path).resolve()
    if not target.exists():
        return {"error": f"Path does not exist: {target}"}

    try:
        os.startfile(str(target))
        logger.info(f"Opened: {target}")
        return {"success": True, "path": str(target)}
    except Exception as e:
        return {"error": f"Failed to open: {str(e)}"}


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
