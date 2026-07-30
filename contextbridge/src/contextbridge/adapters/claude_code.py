from __future__ import annotations
import json
import os
from pathlib import Path
from ..schema import ConversationMessage


def _config_dir() -> Path:
    if env := os.environ.get("CLAUDE_CONFIG_DIR"):
        return Path(env)
    # WSL/Linux 优先 HOME；Windows 走 USERPROFILE；都不在才退回 ~
    if h := os.environ.get("HOME"):
        return Path(h) / ".claude"
    if p := os.environ.get("USERPROFILE"):
        return Path(p) / ".claude"
    return Path(os.path.expanduser("~")) / ".claude"


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("text")
                if t:
                    out.append(t)
                elif block.get("type") == "tool_use":
                    out.append(f"[tool_use: {block.get('name','?')}]")
        return "\n".join(out)
    return str(content)


class ClaudeCodeAdapter:
    name = "claude_code"

    def _projects_dir(self) -> Path:
        return _config_dir() / "projects"

    def detect(self) -> bool:
        return self._projects_dir().exists()

    def get_session_path(self) -> Path | None:
        proj = self._projects_dir()
        if not proj.exists():
            return None
        jsonls = sorted(proj.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return jsonls[0] if jsonls else None

    def parse_session(self) -> list[ConversationMessage]:
        path = self.get_session_path()
        if not path:
            return []
        msgs: list[ConversationMessage] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            m = ev.get("message") or {}
            role = m.get("role") or ev.get("type")
            if role not in ("user", "assistant", "system"):
                continue
            content = _extract_text(m.get("content") or ev.get("content"))
            if not content:
                continue
            msgs.append(ConversationMessage(role=role, content=content))
        return msgs
