"""
JARVIS Core — Conversation Memory

In-memory conversation history with SQLite persistence.
Manages context window for LLM calls.
"""

from dataclasses import dataclass, field
from datetime import datetime
from security.audit_log import audit_log


@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class ConversationMemory:
    """Manages conversation history for LLM context."""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self.history: list[Message] = []
        self.session_id: str = ""

    def set_session(self, session_id: str):
        """Set the current session ID."""
        self.session_id = session_id

    def add_message(self, role: str, content: str):
        """Add a message to history."""
        self.history.append(Message(role=role, content=content))
        # Trim to max_turns (keep system messages)
        non_system = [m for m in self.history if m.role != "system"]
        if len(non_system) > self.max_turns * 2:  # *2 because user+assistant pairs
            # Keep the system messages and the last max_turns pairs
            system_msgs = [m for m in self.history if m.role == "system"]
            recent = non_system[-(self.max_turns * 2):]
            self.history = system_msgs + recent

    def get_messages_for_llm(self, system_prompt: str) -> list[dict]:
        """Get message list formatted for Ollama API."""
        messages = [{"role": "system", "content": system_prompt}]
        for msg in self.history:
            if msg.role != "system":
                messages.append({"role": msg.role, "content": msg.content})
        return messages

    def get_last_user_message(self) -> str | None:
        """Get the most recent user message."""
        for msg in reversed(self.history):
            if msg.role == "user":
                return msg.content
        return None

    async def persist(self):
        """Persist current history to SQLite."""
        if not self.session_id:
            return
        for msg in self.history:
            await audit_log.log_conversation(
                session_id=self.session_id,
                role=msg.role,
                content=msg.content,
            )

    def clear(self):
        """Clear conversation history."""
        self.history.clear()


# Singleton
memory = ConversationMemory()
