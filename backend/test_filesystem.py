"""
Test script for JARVIS Core v0.2.2 Filesystem Truth Layer
"""

import os
import sys
import tempfile
from pathlib import Path
from tools.filesystem import (
    resolve_known_folder,
    list_folders,
    search_files,
    read_text_file,
    read_pdf,
    create_folder,
    delete_file
)

def print_test(name, success, message=""):
    status = "PASS" if success else "FAIL"
    print(f"{name:<40}: {status} {message}")
    return success

def print_skip(name, message=""):
    print(f"{name:<40}: SKIP {message}")

def test_folder_detection():
    print("\n--- 1. Testing Known Folder Detection ---")
    all_ok = True
    for f in ["desktop", "downloads", "documents"]:
        try:
            p = resolve_known_folder(f)
            exists = p.exists() and p.is_dir()
            all_ok = all_ok and print_test(f"Detect {f.capitalize()}", exists, f"Resolved to: {p}")
        except Exception as e:
            all_ok = False
            print_test(f"Detect {f.capitalize()}", False, f"Error: {e}")
    return all_ok

def test_list_downloads():
    print("\n--- 2. Testing List Downloads ---")
    res = list_folders("Downloads")
    # Verify structure
    ok = res.get("success") is True and res.get("verified") is True and res.get("action") == "list_files" and "items" in res
    return print_test("List Downloads", ok, res.get("message", ""))

def test_search_downloads_pdf():
    print("\n--- 3. Testing Search Downloads for PDFs ---")
    res = search_files("Downloads", "pdf")
    ok = res.get("success") is True and res.get("action") == "search_files" and "items" in res
    return print_test("Search Downloads for PDF", ok, res.get("message", ""))

def test_search_desktop_invoice():
    print("\n--- 4. Testing Search Desktop for invoice ---")
    res = search_files("Desktop", "invoice")
    ok = res.get("success") is True and res.get("action") == "search_files"
    return print_test("Search Desktop for invoice", ok, res.get("message", ""))

def test_create_folder():
    print("\n--- 5. Testing Create Folder ---")
    desktop = resolve_known_folder("desktop")
    test_path = desktop / "Jarvis Test"
    
    # Ensure it doesn't already exist for clean test
    if test_path.exists() and test_path.is_dir():
        import shutil
        shutil.rmtree(str(test_path))

    res = create_folder(str(test_path))
    ok = res.get("success") is True and res.get("verified") is True and res.get("action") == "create_folder" and test_path.exists()
    
    # Cleanup
    if test_path.exists():
        import shutil
        shutil.rmtree(str(test_path))
        
    return print_test("Create Desktop Jarvis Test Folder", ok, res.get("message", ""))

def test_read_files():
    print("\n--- 6. Testing Read Files ---")
    all_ok = True
    
    # Temp TXT file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write("Hello from Jarvis TXT test file!")
        txt_path = tf.name
        
    try:
        res = read_text_file(txt_path)
        ok = res.get("success") is True and res.get("content") == "Hello from Jarvis TXT test file!"
        all_ok = all_ok and print_test("Read TXT File", ok, res.get("message", ""))
    finally:
        if os.path.exists(txt_path):
            os.remove(txt_path)
            
    # Temp MD file
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write("# Hello MD\nThis is markdown.")
        md_path = tf.name
        
    try:
        res = read_text_file(md_path)
        ok = res.get("success") is True and "# Hello MD" in res.get("content", "")
        all_ok = all_ok and print_test("Read MD File", ok, res.get("message", ""))
    finally:
        if os.path.exists(md_path):
            os.remove(md_path)
            
    # PDF check
    pdf_path = None
    # Look for any pdf in Downloads to test read_pdf
    downloads = resolve_known_folder("downloads")
    pdfs = list(downloads.glob("*.pdf"))
    if pdfs:
        pdf_path = str(pdfs[0])
        try:
            res = read_pdf(pdf_path)
            ok = res.get("success") is True and "content" in res
            print_test("Read PDF File", ok, f"Successfully read: {pdfs[0].name}")
        except Exception as e:
            print_test("Read PDF File", False, f"Error reading PDF: {e}")
    else:
        print_skip("Read PDF File", "No PDF files found in Downloads folder to test with.")
        
    return all_ok

def test_delete_protection():
    print("\n--- 7. Testing Delete Protection ---")
    res = delete_file("some_dummy_path")
    ok = res.get("success") is False and "Delete is protected" in res.get("message", "")
    return print_test("Delete Protection Blocked", ok, res.get("message", ""))

def main():
    print("=== JARVIS v0.2.2 Filesystem Test Suite ===")
    
    t1 = test_folder_detection()
    t2 = test_list_downloads()
    t3 = test_search_downloads_pdf()
    t4 = test_search_desktop_invoice()
    t5 = test_create_folder()
    t6 = test_read_files()
    t7 = test_delete_protection()
    
    print("\n=== SUMMARY ===")
    results = [t1, t2, t3, t4, t5, t6, t7]
    print(f"Passed: {results.count(True)} / {len(results)}")
    
    if all(results):
        print("\nALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\nSOME TESTS FAILED!")
        sys.exit(1)

if __name__ == "__main__":
    main()
