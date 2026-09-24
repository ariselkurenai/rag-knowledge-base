"""会话记忆：内存态多轮历史（线程安全）

多轮对话的关键：检索前先把「它/这个/上面提到」等指代表达
结合历史改写为独立问题，再进入检索器，否则向量检索会失焦。
"""

import threading
import uuid
from collections import deque
from typing import Optional

from .config import settings


class SessionStore:
    def __init__(self, max_turns: Optional[int] = None):
        self.max_turns = max_turns or settings.max_history_turns
        self._sessions: dict[str, deque] = {}
        self._lock = threading.Lock()

    def new_session(self) -> str:
        session_id = uuid.uuid4().hex[:16]
        with self._lock:
            self._sessions[session_id] = deque(maxlen=self.max_turns * 2)
        return session_id

    def get_history(self, session_id: Optional[str]) -> list[dict]:
        """返回 OpenAI messages 格式的历史；无会话返回空列表"""
        if not session_id:
            return []
        with self._lock:
            session = self._sessions.get(session_id)
            return list(session) if session else []

    def add_turn(self, session_id: Optional[str], question: str, answer: str) -> None:
        if not session_id:
            return
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = deque(maxlen=self.max_turns * 2)
            self._sessions[session_id].append({"role": "user", "content": question})
            self._sessions[session_id].append({"role": "assistant", "content": answer})

    def clear(self, session_id: Optional[str]) -> None:
        if session_id:
            with self._lock:
                self._sessions.pop(session_id, None)

    @property
    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)
