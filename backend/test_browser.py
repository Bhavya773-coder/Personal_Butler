"""
Test script for JARVIS Core v0.2.3 Browser Truth Layer
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path so we can import modules
sys.path.append(str(Path(__file__).parent))

from tools.browser import (
    check_browser_ready,
    launch_browser,
    close_browser,
    open_url,
    search_web,
    open_first_result,
    get_page_content,
    summarize_page,
    is_valid_url_or_domain,
    is_protected_command
)


def print_test(name, success, message=""):
    status = "PASS" if success else "FAIL"
    print(f"{name:<40}: {status} {message}")
    return success


async def run_tests():
    print("=== JARVIS v0.2.3 Browser Test Suite ===")

    # 1. Check browser readiness
    print("\n--- 1. Testing Playwright Readiness ---")
    ready_res = await check_browser_ready()
    ready_ok = ready_res.get("success") is True or "Playwright browser missing" in ready_res.get("message", "")
    print_test("Playwright Readiness Check", ready_ok, ready_res.get("message", ""))

    if not ready_res.get("success"):
        print("\nPlaywright browser not installed. Skipping browser E2E tests.")
        # Test basic url validation and protected command filtering
        print("\n--- Testing URL/Domain Validation and Safety Filters ---")
        t1 = print_test("Validate youtube.com", is_valid_url_or_domain("youtube.com") is True)
        t2 = print_test("Validate https://github.com", is_valid_url_or_domain("https://github.com") is True)
        t3 = print_test("Validate local path invalid", is_valid_url_or_domain("C:\\path\\to\\file") is False)
        t4 = print_test("Validate spaces invalid", is_valid_url_or_domain("search for cars") is False)
        t5 = print_test("Protected login block", is_protected_command("login to my bank") is True)
        t6 = print_test("Protected pay block", is_protected_command("pay $50 to someone") is True)
        t7 = print_test("Protected submit block", is_protected_command("submit this form") is True)
        
        all_passed = ready_ok and all([t1, t2, t3, t4, t5, t6, t7])
        sys.exit(0 if all_passed else 1)

    # 2. Open browser
    print("\n--- 2. Testing Open Browser ---")
    launch_res = await launch_browser(headless=True)
    launch_ok = launch_res.get("success") is True and launch_res.get("verified") is True
    print_test("Launch Headless Browser", launch_ok, launch_res.get("message", ""))

    # 3. Search for "electric excavators in India"
    print("\n--- 3. Testing Search 1 ---")
    search1_res = await search_web("electric excavators in India", engine="duckduckgo")
    search1_ok = (
        search1_res.get("success") is True and 
        len(search1_res.get("results", [])) > 0
    )
    print_test("Search Electric Excavators", search1_ok, f"Found {len(search1_res.get('results', []))} results")

    # 4. Search for "Gujarat tourism subsidy"
    print("\n--- 4. Testing Search 2 ---")
    search2_res = await search_web("Gujarat tourism subsidy", engine="duckduckgo")
    search2_ok = (
        search2_res.get("success") is True and 
        len(search2_res.get("results", [])) > 0
    )
    print_test("Search Gujarat Tourism", search2_ok, f"Found {len(search2_res.get('results', []))} results")

    # 5. Open youtube.com (with protocol validation)
    print("\n--- 5. Testing URL Prepends & Opening ---")
    yt_res = await open_url("youtube.com")
    yt_ok = yt_res.get("success") is True and "youtube" in yt_res.get("url", "")
    print_test("Open youtube.com (prepend https://)", yt_ok, f"Loaded URL: {yt_res.get('url')}")

    # Restore search results cache so we can test first result open
    await search_web("Gujarat tourism", engine="duckduckgo")

    # 6. Open first result after search
    print("\n--- 6. Testing Open First Result ---")
    first_res = await open_first_result(index=0)
    first_ok = first_res.get("success") is True and first_res.get("url") is not None
    print_test("Open First Search Result", first_ok, f"Loaded URL: {first_res.get('url')} - Title: {first_res.get('title')}")

    # 7. Extract current page text
    print("\n--- 7. Testing Extract Page Content ---")
    extract_res = await get_page_content(max_chars=8000)
    extract_ok = (
        extract_res.get("success") is True and 
        extract_res.get("text_preview") is not None and 
        len(extract_res.get("text_preview", "")) <= 8000
    )
    print_test("Extract Text (limit 8000 chars)", extract_ok, f"Extracted {len(extract_res.get('text_preview', ''))} characters")

    # 8. Summarize page (with Ollama unavailable fallback)
    print("\n--- 8. Testing Summarization Fallback ---")
    summary_res = await summarize_page(ollama_summary=True)
    summary_ok = (
        summary_res.get("success") is True and 
        summary_res.get("text_preview") is not None
    )
    is_fallback = "Ollama is unavailable" in summary_res.get("message", "")
    print_test("Summarize Page (with Fallback)", summary_ok, "Fallback active: " + str(is_fallback))

    # 9. Vague command does not route as URL
    print("\n--- 9. Testing URL Domain Validation ---")
    v1 = is_valid_url_or_domain("video open I am not able to see any note")
    v2 = is_valid_url_or_domain("google.com")
    validation_ok = (v1 is False) and (v2 is True)
    print_test("Vague URL Validation Blocked", validation_ok, f"'video open...' -> {v1}, 'google.com' -> {v2}")

    # 10. Protected submit/login/payment commands are blocked
    print("\n--- 10. Testing Protected Action Blocking ---")
    p1 = is_protected_command("login to my bank")
    p2 = is_protected_command("submit this form")
    p3 = is_protected_command("make payment of 100 dollars")
    safety_ok = p1 and p2 and p3
    print_test("Protected Action Filtering", safety_ok, f"login: {p1}, submit: {p2}, pay: {p3}")

    # Close browser
    await close_browser()
    
    print("\n=== SUMMARY ===")
    results = [ready_res.get("success"), launch_ok, search1_ok, search2_ok, yt_ok, first_ok, extract_ok, summary_ok, validation_ok, safety_ok]
    passed = results.count(True)
    print(f"Passed: {passed} / {len(results)}")
    
    if all(results):
        print("\nALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\nSOME TESTS FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
