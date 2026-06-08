"""
JARVIS Core — Filesystem Tools

Safe file system operations with pathlib for Windows compatibility.
All filesystem tool functions return structured results.
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger("jarvis.tools.filesystem")


def resolve_known_folder(folder_name: str) -> Path:
    """Resolve Desktop, Downloads, or Documents folders, with OneDrive fallback."""
    folder_name_lower = folder_name.lower().strip()
    home = Path.home()
    
    if "desktop" in folder_name_lower:
        p1 = home / "Desktop"
        p2 = home / "OneDrive" / "Desktop"
    elif "download" in folder_name_lower:
        p1 = home / "Downloads"
        p2 = home / "OneDrive" / "Downloads"
    elif "document" in folder_name_lower:
        p1 = home / "Documents"
        p2 = home / "OneDrive" / "Documents"
    else:
        raise FileNotFoundError(f"Unknown folder: {folder_name}")

    if p1.exists() and p1.is_dir():
        return p1
    if p2.exists() and p2.is_dir():
        return p2
        
    raise FileNotFoundError(f"Folder '{folder_name}' not found on this system.")


def resolve_path(path_str: str) -> Path:
    """Resolve a path string, expanding environment variables, user directories, and handling Desktop/Downloads/Documents aliases."""
    expanded = os.path.expandvars(os.path.expanduser(path_str.strip()))
    
    # Check if it's one of the known folders
    lower_path = path_str.lower().strip()
    if lower_path in ["desktop", "downloads", "documents"]:
        return resolve_known_folder(lower_path)
    
    # Or starts with desktop, downloads, documents as a separate segment
    for prefix in ["desktop", "downloads", "documents"]:
        if lower_path.startswith(prefix + "/") or lower_path.startswith(prefix + "\\"):
            remainder = path_str[len(prefix)+1:]
            base = resolve_known_folder(prefix)
            return (base / remainder).resolve()

    return Path(expanded).resolve()


def is_safe_search_path(target_path: Path) -> bool:
    """Check if the path is safe to search (under Desktop, Downloads, or Documents, or an explicit user subfolder)."""
    if target_path.drive and target_path == Path(target_path.drive).resolve():
        return False
        
    try:
        desktop = resolve_known_folder("desktop")
        downloads = resolve_known_folder("downloads")
        documents = resolve_known_folder("documents")
    except FileNotFoundError:
        return False
        
    # Check if target is inside desktop, downloads, or documents
    try:
        is_under_known = (
            target_path.is_relative_to(desktop) or
            target_path.is_relative_to(downloads) or
            target_path.is_relative_to(documents)
        )
        if is_under_known:
            return True
    except ValueError:
        pass
        
    # If not under known folders, check if it's a specific deep subfolder in C:\Users (not C:\ directly)
    userprofile = Path(os.getenv("USERPROFILE", os.path.expanduser("~"))).resolve()
    try:
        if target_path.is_relative_to(userprofile) and target_path != userprofile:
            return True
    except ValueError:
        pass
        
    return False


def list_folders(path: str, recursive: bool = False) -> dict:
    """List contents of a directory (max 20 items, non-recursive by default)."""
    try:
        target = resolve_path(path)
    except FileNotFoundError as e:
        return {
            "success": False,
            "verified": False,
            "action": "list_files",
            "target": path,
            "message": str(e),
            "items": [],
            "count": 0,
            "error": str(e)
        }

    # Safety check: do not scan root drive
    if target.drive and target == Path(target.drive).resolve():
        err = "Listing the root directory of a drive is blocked for safety. Please specify a subfolder."
        return {
            "success": False,
            "verified": False,
            "action": "list_files",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    if not target.exists():
        err = f"Path does not exist: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "list_files",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }
    if not target.is_dir():
        err = f"Path is not a directory: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "list_files",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    items = []
    try:
        iterator = target.rglob("*") if recursive else target.iterdir()
        for item in sorted(iterator):
            try:
                info = {
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None,
                    "extension": item.suffix.lower() if item.is_file() else "",
                    "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat() if hasattr(item, "stat") else ""
                }
                items.append(info)
            except PermissionError:
                continue
    except PermissionError:
        err = f"Permission denied: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "list_files",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    limited_items = items[:20]
    count = len(limited_items)
    
    if len(items) == 0:
        msg = f"Folder is empty: {target}"
    else:
        msg = f"Contents of {target} ({count} items shown out of {len(items)}):"

    return {
        "success": True,
        "verified": True,
        "action": "list_files",
        "target": str(target),
        "message": msg,
        "items": limited_items,
        "count": len(items),
        "error": None
    }


def search_files(path: str, pattern: str, recursive: bool = False, confirmed: bool = False) -> dict:
    """Search for files matching a glob pattern (non-recursive by default)."""
    try:
        target = resolve_path(path)
    except FileNotFoundError as e:
        return {
            "success": False,
            "verified": False,
            "action": "search_files",
            "target": path,
            "message": str(e),
            "items": [],
            "count": 0,
            "error": str(e)
        }

    # Safety checks
    if not is_safe_search_path(target):
        err = f"Searching in '{target}' is blocked for safety. You can only search Desktop, Downloads, Documents, or user subfolders."
        return {
            "success": False,
            "verified": False,
            "action": "search_files",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    if not target.exists():
        err = f"Path does not exist: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "search_files",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    # Recursive check
    if recursive and not confirmed:
        return {
            "success": False,
            "verified": False,
            "action": "search_files",
            "target": str(target),
            "message": "Recursive search requires confirmation.",
            "error": "Recursive search requires confirmation.",
            "requires_confirmation": True
        }

    try:
        pat = pattern.strip()
        
        # Check extensions mapping
        ext_map = {
            "pdf": ["*.pdf"],
            "excel": ["*.xls", "*.xlsx", "*.csv"],
            "word": ["*.doc", "*.docx"],
            "image": ["*.jpg", "*.jpeg", "*.png", "*.webp"],
            "photo": ["*.jpg", "*.jpeg", "*.png", "*.webp"],
            "video": ["*.mp4", "*.mov", "*.avi", "*.mkv"],
            "text": ["*.txt"],
            "markdown": ["*.md"]
        }
        
        pat_lower = pat.lower()
        globs = [pat]
        if pat_lower in ext_map:
            globs = ext_map[pat_lower]
        elif pat_lower.startswith("."):
            globs = [f"*{pat}"]
        elif not any(char in pat for char in ["*", "?"]):
            globs = [f"*{pat}*"]

        matches = []
        for g in globs:
            if recursive:
                matches.extend(list(target.rglob(g)))
            else:
                matches.extend(list(target.glob(g)))

        results = []
        seen_paths = set()
        for m in matches:
            resolved_m = m.resolve()
            if resolved_m in seen_paths:
                continue
            seen_paths.add(resolved_m)
            
            try:
                results.append({
                    "name": m.name,
                    "path": str(m),
                    "is_dir": m.is_dir(),
                    "size": m.stat().st_size if m.is_file() else None,
                    "extension": m.suffix.lower() if m.is_file() else "",
                    "modified": datetime.fromtimestamp(m.stat().st_mtime).isoformat() if hasattr(m, "stat") else ""
                })
            except PermissionError:
                continue

        results.sort(key=lambda x: x["name"].lower())
        limited_results = results[:20]
        count = len(limited_results)
        
        if len(results) == 0:
            msg = "No matching files found."
        else:
            msg = f"Found {len(results)} file(s) matching '{pattern}' in {target} ({count} shown):"

        return {
            "success": True,
            "verified": True,
            "action": "search_files",
            "target": str(target),
            "message": msg,
            "items": limited_results,
            "count": len(results),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "action": "search_files",
            "target": str(target),
            "message": f"Search failed: {str(e)}",
            "items": [],
            "count": 0,
            "error": str(e)
        }


def read_text_file(path: str, max_chars: int = 20000) -> dict:
    """Read a text or markdown file (max 20,000 characters)."""
    try:
        target = resolve_path(path)
    except FileNotFoundError as e:
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": path,
            "message": str(e),
            "items": [],
            "count": 0,
            "error": str(e)
        }

    if not target.exists():
        err = f"File does not exist: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }
    if not target.is_file():
        err = f"Path is not a file: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    # Supported extension check
    suffix = target.suffix.lower()
    if suffix not in [".txt", ".md"]:
        err = f"Unsupported file type '{suffix}'. Jarvis can only read .txt, .md, and .pdf files."
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > max_chars
        return {
            "success": True,
            "verified": True,
            "action": "read_file",
            "target": str(target),
            "message": f"Read file {target.name} successfully.",
            "content": content[:max_chars],
            "truncated": truncated,
            "items": [],
            "count": len(content[:max_chars]),
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": f"Cannot read file: {str(e)}",
            "items": [],
            "count": 0,
            "error": str(e)
        }


def read_pdf(path: str, max_pages: int = 10) -> dict:
    """Read text from a PDF file (max 10 pages)."""
    try:
        target = resolve_path(path)
    except FileNotFoundError as e:
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": path,
            "message": str(e),
            "items": [],
            "count": 0,
            "error": str(e)
        }

    if not target.exists():
        err = f"File does not exist: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }
    if not target.is_file():
        err = f"Path is not a file: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    suffix = target.suffix.lower()
    if suffix != ".pdf":
        err = f"Unsupported file type '{suffix}'. This function only reads PDF files."
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(target))
        pages_text = []
        for i, page in enumerate(reader.pages[:max_pages]):
            text = page.extract_text() or ""
            pages_text.append({"page": i + 1, "text": text.strip()})

        content = "\n\n".join([f"[Page {p['page']}]\n{p['text']}" for p in pages_text])
        return {
            "success": True,
            "verified": True,
            "action": "read_file",
            "target": str(target),
            "message": f"Read PDF file {target.name} successfully.",
            "content": content,
            "pages": pages_text,
            "total_pages": len(reader.pages),
            "pages_read": len(pages_text),
            "items": [],
            "count": len(pages_text),
            "error": None
        }
    except ImportError:
        err = "PyPDF2 is not installed. Please run: pip install PyPDF2"
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "action": "read_file",
            "target": str(target),
            "message": f"Cannot read PDF: {str(e)}",
            "items": [],
            "count": 0,
            "error": str(e)
        }


def create_folder(path: str) -> dict:
    """Create a new folder (including parent directories)."""
    try:
        target = resolve_path(path)
    except FileNotFoundError as e:
        return {
            "success": False,
            "verified": False,
            "action": "create_folder",
            "target": path,
            "message": str(e),
            "items": [],
            "count": 0,
            "error": str(e)
        }

    if target.drive and target == Path(target.drive).resolve():
        err = "Modifying the root directory of a drive is blocked for safety."
        return {
            "success": False,
            "verified": False,
            "action": "create_folder",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }
    if target.exists():
        err = f"Path already exists: {target}"
        return {
            "success": False,
            "verified": False,
            "action": "create_folder",
            "target": str(target),
            "message": err,
            "items": [],
            "count": 0,
            "error": err
        }

    try:
        target.mkdir(parents=True, exist_ok=True)
        # Verify folder exists!
        if target.exists() and target.is_dir():
            logger.info(f"Created folder: {target}")
            return {
                "success": True,
                "verified": True,
                "action": "create_folder",
                "target": str(target),
                "message": f"Created folder: {target.name}.",
                "error": None
            }
        else:
            err = f"I tried to create the folder {target.name}, but Windows did not create it."
            return {
                "success": False,
                "verified": False,
                "action": "create_folder",
                "target": str(target),
                "message": err,
                "items": [],
                "count": 0,
                "error": "Folder existence verification failed."
            }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "action": "create_folder",
            "target": str(target),
            "message": f"Cannot create folder: {str(e)}",
            "items": [],
            "count": 0,
            "error": str(e)
        }


def copy_file(source: str, destination: str) -> dict:
    """Copy a file or directory."""
    src = Path(source).resolve()
    dst = Path(destination).resolve()

    if not src.exists():
        return {"error": f"Source does not exist: {src}"}

    try:
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
        logger.info(f"Copied: {src} → {dst}")
        return {"success": True, "source": str(src), "destination": str(dst)}
    except Exception as e:
        return {"error": f"Copy failed: {str(e)}"}


def move_file(source: str, destination: str) -> dict:
    """Move a file or directory."""
    src = Path(source).resolve()
    dst = Path(destination).resolve()

    if not src.exists():
        return {"error": f"Source does not exist: {src}"}

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        logger.info(f"Moved: {src} → {dst}")
        return {"success": True, "source": str(src), "destination": str(dst)}
    except Exception as e:
        return {"error": f"Move failed: {str(e)}"}


def rename_file(path: str, new_name: str) -> dict:
    """Rename a file or directory."""
    target = Path(path).resolve()
    if not target.exists():
        return {"error": f"Path does not exist: {target}"}

    new_path = target.parent / new_name
    if new_path.exists():
        return {"error": f"Target name already exists: {new_path}"}

    try:
        target.rename(new_path)
        logger.info(f"Renamed: {target} → {new_path}")
        return {"success": True, "old_path": str(target), "new_path": str(new_path)}
    except Exception as e:
        return {"error": f"Rename failed: {str(e)}"}


def delete_file(path: str, confirmed: bool = False) -> dict:
    """Delete is protected for this phase."""
    target = Path(path).resolve()
    return {
        "success": False,
        "verified": False,
        "action": "delete_file",
        "target": str(target),
        "message": "Delete is protected. I will not delete files until dangerous confirmation is fully implemented.",
        "error": "Delete is protected."
    }


def get_desktop_path() -> Path:
    """Get the user's Desktop folder path."""
    return resolve_known_folder("desktop")


def get_downloads_path() -> Path:
    """Get the user's Downloads folder path."""
    return resolve_known_folder("downloads")


def get_documents_path() -> Path:
    """Get the user's Documents folder path."""
    return resolve_known_folder("documents")
