"""
JARVIS Core — Security Permission Engine

Three-tier permission model:
  SAFE     → execute immediately
  CONFIRM  → ask user confirmation via UI
  DANGEROUS → require explicit user confirmation, warn strongly
"""

import asyncio
import uuid
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


class PermissionLevel(str, Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"


@dataclass
class PermissionRequest:
    """A pending permission request waiting for user response."""
    id: str
    action: str
    description: str
    level: PermissionLevel
    details: dict
    created_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    approved: Optional[bool] = None
    _event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)


# ── Action → Permission Level Mapping ──────────────────────────────────

ACTION_PERMISSIONS: dict[str, PermissionLevel] = {
    # SAFE actions
    "system_info": PermissionLevel.SAFE,
    "get_cpu_usage": PermissionLevel.SAFE,
    "get_ram_usage": PermissionLevel.SAFE,
    "get_disk_usage": PermissionLevel.SAFE,
    "open_application": PermissionLevel.SAFE,
    "search_web": PermissionLevel.SAFE,
    "open_url": PermissionLevel.SAFE,
    "get_page_content": PermissionLevel.SAFE,
    "get_search_results": PermissionLevel.SAFE,
    "list_folders": PermissionLevel.SAFE,
    "search_files": PermissionLevel.SAFE,
    "launch_browser": PermissionLevel.SAFE,
    "close_browser": PermissionLevel.SAFE,
    "read_text_file": PermissionLevel.SAFE,
    "read_pdf": PermissionLevel.SAFE,

    # CONFIRM actions
    "create_folder": PermissionLevel.CONFIRM,
    "copy_file": PermissionLevel.CONFIRM,
    "move_file": PermissionLevel.CONFIRM,
    "rename_file": PermissionLevel.CONFIRM,
    "take_screenshot": PermissionLevel.CONFIRM,
    "type_text": PermissionLevel.CONFIRM,
    "press_keys": PermissionLevel.CONFIRM,
    "click_link": PermissionLevel.CONFIRM,
    "fill_form": PermissionLevel.CONFIRM,
    "open_file_or_folder": PermissionLevel.CONFIRM,

    # DANGEROUS actions
    "delete_file": PermissionLevel.DANGEROUS,
    "run_shell": PermissionLevel.DANGEROUS,
    "install_software": PermissionLevel.DANGEROUS,
    "change_system_settings": PermissionLevel.DANGEROUS,
    "submit_form": PermissionLevel.DANGEROUS,
    "login_action": PermissionLevel.DANGEROUS,
    "payment_action": PermissionLevel.DANGEROUS,
    "send_message": PermissionLevel.DANGEROUS,
}


class PermissionEngine:
    """Manages permission checking and confirmation requests."""

    def __init__(self):
        self._pending: dict[str, PermissionRequest] = {}

    def get_level(self, action: str) -> PermissionLevel:
        """Get the permission level for a given action."""
        return ACTION_PERMISSIONS.get(action, PermissionLevel.CONFIRM)

    def is_safe(self, action: str) -> bool:
        """Check if an action can be executed without confirmation."""
        return self.get_level(action) == PermissionLevel.SAFE

    async def request_permission(
        self,
        action: str,
        description: str,
        details: dict | None = None,
        timeout: float = 60.0,
    ) -> bool:
        """
        Create a permission request and wait for user approval.
        Returns True if approved, False if denied or timed out.
        """
        level = self.get_level(action)
        if level == PermissionLevel.SAFE:
            return True

        request = PermissionRequest(
            id=str(uuid.uuid4()),
            action=action,
            description=description,
            level=level,
            details=details or {},
        )
        self._pending[request.id] = request

        try:
            await asyncio.wait_for(request._event.wait(), timeout=timeout)
            return request.approved or False
        except asyncio.TimeoutError:
            request.resolved = True
            request.approved = False
            return False
        finally:
            self._pending.pop(request.id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        """Resolve a pending permission request."""
        request = self._pending.get(request_id)
        if not request or request.resolved:
            return False

        request.resolved = True
        request.approved = approved
        request._event.set()
        return True

    def get_pending(self) -> list[dict]:
        """Get all pending permission requests as dicts."""
        return [
            {
                "id": r.id,
                "action": r.action,
                "description": r.description,
                "level": r.level.value,
                "details": r.details,
                "created_at": r.created_at.isoformat(),
            }
            for r in self._pending.values()
            if not r.resolved
        ]

    def deny_all(self):
        """Deny all pending permissions (used on interrupt)."""
        for request in self._pending.values():
            if not request.resolved:
                request.resolved = True
                request.approved = False
                request._event.set()


# Singleton instance
permission_engine = PermissionEngine()
