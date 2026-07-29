from __future__ import annotations
from pathlib import Path
from ..schema import ConversationMessage


class GenericAdapter:
    """Fallback adapter: conversation is passed in as a list of dicts."""

    name = "generic"
    _conversation: list[dict] = []

    def set_conversation(self, conv: list[dict]) -> None:
        self._conversation = conv

    def detect(self) -> bool:
        return True

    def get_session_path(self) -> Path | None:
        return None

    def parse(self, conversation: list[dict] | None = None) -> list[ConversationMessage]:
        conv = conversation if conversation is not None else self._conversation
        return [ConversationMessage(**m) for m in conv]

    def parse_session(self) -> list[ConversationMessage]:
        return self.parse()

    def get_open_files(self) -> list[str]:
        return []
