"""
Test script for JARVIS Core v0.2.1 App Launch Verification
"""

import asyncio
import sys
from tools.pc_control import PCControlTool

async def test_app(tool: PCControlTool, name: str):
    print(f"\n--- Testing open_app('{name}') ---")
    try:
        res = await tool.open_app(name)
        print(f"Result: {res}")
        if res.get("success") and res.get("verified"):
            print(f"PASS: {name} launched and verified successfully.")
            return True
        else:
            print(f"FAIL: {name} launch/verification failed. Message: {res.get('message')}")
            return False
    except Exception as e:
        print(f"ERROR: Exception while launching {name}: {e}")
        return False

async def test_folder(tool: PCControlTool, name: str):
    print(f"\n--- Testing open_folder('{name}') ---")
    try:
        res = await tool.open_folder(name)
        print(f"Result: {res}")
        if res.get("success") and res.get("verified"):
            print(f"PASS: {name} folder opened and verified successfully.")
            return True
        else:
            print(f"FAIL: {name} folder opening/verification failed. Message: {res.get('message')}")
            return False
    except Exception as e:
        print(f"ERROR: Exception while opening folder {name}: {e}")
        return False

async def main():
    print("=== JARVIS v0.2.1 App Launch Test Suite ===")
    tool = PCControlTool()
    
    # 1. PCControlTool open_app notepad
    notepad_ok = await test_app(tool, "notepad")
    
    # 2. PCControlTool open_app calculator
    calc_ok = await test_app(tool, "calculator")
    
    # 3. PCControlTool open_app chrome
    chrome_ok = await test_app(tool, "chrome")
    
    # 4. PCControlTool open_folder downloads
    downloads_ok = await test_folder(tool, "downloads")
    
    # 5. PCControlTool open_folder desktop
    desktop_ok = await test_folder(tool, "desktop")
    
    print("\n=== SUMMARY ===")
    print(f"Notepad Launch:    {'PASS' if notepad_ok else 'FAIL'}")
    print(f"Calculator Launch: {'PASS' if calc_ok else 'FAIL'}")
    print(f"Chrome Launch:     {'PASS' if chrome_ok else 'FAIL'}")
    print(f"Downloads Open:    {'PASS' if downloads_ok else 'FAIL'}")
    print(f"Desktop Open:      {'PASS' if desktop_ok else 'FAIL'}")
    
    if all([notepad_ok, calc_ok, chrome_ok, downloads_ok, desktop_ok]):
        print("\nALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\nSOME TESTS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
