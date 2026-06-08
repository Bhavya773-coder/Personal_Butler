"""
JARVIS Core — Filesystem Tools

Safe file system operations with pathlib for Windows compatibility.
All destructive operations require explicit confirmation flag.
"""

import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.tools.filesystem")


def list_folders(path: str) -> dict:
    """List contents of a directory."""
    target = Path(path).resolve()
    if target.drive and target == Path(target.drive).resolve():
        return {"error": "Listing the root directory of a drive is blocked for safety. Please specify a subfolder."}
    if not target.exists():
        return {"error": f"Path does not exist: {target}"}
    if not target.is_dir():
        return {"error": f"Path is not a directory: {target}"}

    items = []
    try:
        for item in sorted(target.iterdir()):
            try:
                info = {
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None,
                }
                items.append(info)
            except PermissionError:
                items.append({"name": item.name, "path": str(item), "error": "permission denied"})
    except PermissionError:
        return {"error": f"Permission denied: {target}"}

    return {
        "path": str(target),
        "count": len(items),
        "items": items,
    }


def search_files(path: str, pattern: str, recursive: bool = True) -> dict:
    """Search for files matching a glob pattern."""
    target = Path(path).resolve()
    if target.drive and target == Path(target.drive).resolve():
        return {"error": "Searching the root directory of a drive is blocked for safety. Please specify a subfolder."}
    if not target.exists():
        return {"error": f"Path does not exist: {target}"}

    try:
        if recursive:
            matches = list(target.rglob(pattern))
        else:
            matches = list(target.glob(pattern))

        results = []
        for m in matches[:100]:  # Limit to 100 results
            try:
                results.append({
                    "name": m.name,
                    "path": str(m),
                    "is_dir": m.is_dir(),
                    "size": m.stat().st_size if m.is_file() else None,
                })
            except PermissionError:
                continue

        return {
            "search_path": str(target),
            "pattern": pattern,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        return {"error": str(e)}


def read_text_file(path: str, max_chars: int = 10000) -> dict:
    """Read a text file (txt, md, py, json, etc.)."""
    target = Path(path).resolve()
    if not target.exists():
        return {"error": f"File does not exist: {target}"}
    if not target.is_file():
        return {"error": f"Path is not a file: {target}"}

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > max_chars
        return {
            "path": str(target),
            "size": target.stat().st_size,
            "content": content[:max_chars],
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": f"Cannot read file: {str(e)}"}


def read_pdf(path: str, max_pages: int = 10) -> dict:
    """Read text from a PDF file using PyPDF2."""
    target = Path(path).resolve()
    if not target.exists():
        return {"error": f"File does not exist: {target}"}

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(target))
        pages_text = []
        for i, page in enumerate(reader.pages[:max_pages]):
            text = page.extract_text() or ""
            pages_text.append({"page": i + 1, "text": text.strip()})

        return {
            "path": str(target),
            "total_pages": len(reader.pages),
            "pages_read": len(pages_text),
            "pages": pages_text,
        }
    except ImportError:
        return {"error": "PyPDF2 not installed. Run: pip install PyPDF2"}
    except Exception as e:
        return {"error": f"Cannot read PDF: {str(e)}"}


def create_folder(path: str) -> dict:
    """Create a new folder (including parent directories)."""
    target = Path(path).resolve()
    if target.drive and target == Path(target.drive).resolve():
        return {"error": "Modifying the root directory of a drive is blocked for safety."}
    if target.exists():
        return {"error": f"Path already exists: {target}", "path": str(target)}

    try:
        target.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created folder: {target}")
        return {"success": True, "path": str(target)}
    except Exception as e:
        return {"error": f"Cannot create folder: {str(e)}"}


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
    """Delete a file or directory. REQUIRES confirmed=True."""
    if not confirmed:
        return {"error": "Deletion requires explicit confirmation.", "requires_confirmation": True}

    target = Path(path).resolve()
    if target.drive and target == Path(target.drive).resolve():
        return {"error": "Deleting the root directory of a drive is blocked for safety."}
    if not target.exists():
        return {"error": f"Path does not exist: {target}"}

    try:
        if target.is_dir():
            shutil.rmtree(str(target))
        else:
            target.unlink()
        logger.info(f"Deleted: {target}")
        return {"success": True, "deleted": str(target)}
    except Exception as e:
        return {"error": f"Delete failed: {str(e)}"}


def get_desktop_path() -> Path:
    """Get the user's Desktop folder path."""
    return Path.home() / "Desktop"


def get_downloads_path() -> Path:
    """Get the user's Downloads folder path."""
    return Path.home() / "Downloads"


def get_documents_path() -> Path:
    """Get the user's Documents folder path."""
    return Path.home() / "Documents"
