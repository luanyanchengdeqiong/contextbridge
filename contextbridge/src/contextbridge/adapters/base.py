from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable
from ..schema import ConversationMessage


@runtime_checkable
class SourceAdapter(Protocol):
    name: str

    def detect(self) -> bool: ...
    def get_session_path(self) -> Path | None: ...
    def parse_session(self) -> list[ConversationMessage]: ...


__all__ = ["SourceAdapter", "ConversationMessage"]
