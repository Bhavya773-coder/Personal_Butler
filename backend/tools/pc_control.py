"""
JARVIS Core — PC Control Tools

Open applications, take screenshots, type text, keyboard automation.
Dangerous operations require explicit confirmation.
"""

import os
import subprocess
import logging
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


def open_application(name: str) -> dict:
    """Open an application by name."""
    name_lower = name.lower().strip()
    executable = APP_MAP.get(name_lower)

    if not executable:
        # Try running the name directly
        executable = name_lower

    try:
        if executable.startswith("ms-"):
            # Windows URI scheme
            os.startfile(executable)
        else:
            # Use subprocess to launch without blocking
            subprocess.Popen(
                executable,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        logger.info(f"Opened application: {name} ({executable})")
        return {"success": True, "application": name, "executable": executable}
    except FileNotFoundError:
        return {"error": f"Application not found: {name}. Make sure it's installed and in PATH."}
    except Exception as e:
        return {"error": f"Failed to open {name}: {str(e)}"}


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
