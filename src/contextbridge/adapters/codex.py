from __future__ import annotations
import json
import os
from pathlib import Path
from ..schema import ConversationMessage


def _home() -> Path:
    """Codex CLI 数据目录。"""
    if env := os.environ.get("CODEX_HOME"):
        return Path(env)
    if p := os.environ.get("USERPROFILE"):
        return Path(p) / ".codex"
    if h := os.environ.get("HOME"):
        return Path(h) / ".codex"
    return Path(os.path.expanduser("~")) / ".codex"


def _extract_text(content) -> str:
    """从 response_item.content 里提取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict):
                t = block.get("text") or block.get("input_text")
                if t:
                    out.append(t)
        return "\n".join(out)
    return str(content) if content is not None else ""


# Codex 的 developer role 是系统指令(等价于 system),映射成 system 以保持 schema 一致
_ROLE_MAP = {"developer": "system", "tool": "system"}


class CodexAdapter:
    """读取 Codex CLI 的 rollout 会话文件。

    会话保存在 ``~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl``,以事件流形式。
    真实对话消息是 ``response_item`` 事件,其 ``payload`` 含 ``role`` 与 ``content``。
    每条 response_item 是一条独立消息(增量),因此逐行解析即可。
    ``developer`` 是系统指令,映射为 ``system``;``function_call`` 等无 role 的项跳过。
    """

    name = "codex"

    def _sessions_dir(self) -> Path:
        return _home() / "sessions"

    def detect(self) -> bool:
        return self._sessions_dir().exists()

    def get_session_path(self) -> Path | None:
        sessions = self._sessions_dir()
        if not sessions.exists():
            return None
        jsonls = sorted(
            sessions.rglob("rollout-*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return jsonls[0] if jsonls else None

    def parse_session(self) -> list[ConversationMessage]:
        path = self.get_session_path()
        if not path:
            return []

        out: list[ConversationMessage] = []
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    if ev.get("type") != "response_item":
                        continue
                    payload = ev.get("payload") or {}
                    if payload.get("type") != "message":
                        # 仅采集 message,跳过 function_call / function_call_output
                        continue
                    raw_role = payload.get("role")
                    if not raw_role:
                        continue
                    role = _ROLE_MAP.get(raw_role, raw_role)
                    if role not in ("user", "assistant", "system"):
                        continue
                    content = _extract_text(payload.get("content"))
                    if not content:
                        continue
                    out.append(ConversationMessage(role=role, content=content))
        except OSError:
            return []
        return out

    def get_open_files(self) -> list[str]:
        return []
