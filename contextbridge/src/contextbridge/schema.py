from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None


class SourceInfo(BaseModel):
    ide: str
    version: Optional[str] = None
    cwd: Optional[str] = None


class Snapshot(BaseModel):
    version: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: Optional[str] = None
    source: SourceInfo
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    summary: Optional[str] = None
    conversation: list[ConversationMessage]
    git_diff: Optional[str] = None
    open_files: list[str] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        if not self.title:
            first_user = next(
                (m.content for m in self.conversation if m.role == "user"), ""
            )
            self.title = first_user[:60] or "untitled"
        if self.summary is None:
            first_user = next(
                (m.content for m in self.conversation if m.role == "user"), ""
            )
            self.summary = first_user[:200]
