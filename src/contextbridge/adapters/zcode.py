from __future__ import annotations
import json
import os
from pathlib import Path
from ..schema import ConversationMessage


def _home() -> Path:
    """ZCode CLI 数据目录。"""
    if env := os.environ.get("ZCODE_HOME"):
        return Path(env)
    if p := os.environ.get("USERPROFILE"):
        return Path(p) / ".zcode"
    if h := os.environ.get("HOME"):
        return Path(h) / ".zcode"
    return Path(os.path.expanduser("~")) / ".zcode"


def _extract_text(content) -> str:
    """从 message.content 里提取纯文本。"""
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


class ZCodeAdapter:
    """读取 ZCode CLI 的 transcript.jsonl。

    ZCode 把会话事件流写到 ``~/.zcode/cli/agents/sess_*/agent_*/transcript.jsonl``。
    真实对话保存在 ``model_request`` 事件的 ``payload.messages`` 里,且每次请求带
    的是当前累积快照(非增量),因此取时间最新的那条 model_request 即可。
    """

    name = "zcode"

    def _agents_dir(self) -> Path:
        return _home() / "cli" / "agents"

    def detect(self) -> bool:
        return self._agents_dir().exists()

    def get_session_path(self) -> Path | None:
        agents = self._agents_dir()
        if not agents.exists():
            return None
        # 选 mtime 最新的 transcript.jsonl(主对话 / subagent 都参与,主对话通常最大)
        jsonls = sorted(
            agents.rglob("transcript.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return jsonls[0] if jsonls else None

    def parse_session(self) -> list[ConversationMessage]:
        path = self.get_session_path()
        if not path:
            return []

        # 找最后一条 model_request(最新、最完整的消息快照)
        last_messages: list[dict] = []
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
                    if ev.get("type") != "model_request":
                        continue
                    msgs = (ev.get("payload") or {}).get("messages")
                    if isinstance(msgs, list) and msgs:
                        last_messages = msgs
        except OSError:
            return []

        out: list[ConversationMessage] = []
        for m in last_messages:
            role = m.get("role")
            if role not in ("user", "assistant", "system"):
                # 跳过 tool / developer 等非对话角色
                continue
            content = _extract_text(m.get("content"))
            if not content:
                continue
            out.append(ConversationMessage(role=role, content=content))
        return out

    def get_open_files(self) -> list[str]:
        return []
