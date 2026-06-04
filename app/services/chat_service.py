"""
app/services/chat_service.py
─────────────────────────────
Adapter: wraps the existing Orchestrator so the new UI can call
    chat_service.chat(prompt, run_quality_check) -> ChatResponse
"""
from __future__ import annotations
from dataclasses import dataclass
from app.agents.orchestrator import Orchestrator


@dataclass
class ChatResponse:
    answer: str
    tool_used: str | None = None
    sources: list = None
    tool_result: object = None
    metrics: dict | None = None

    def __str__(self) -> str:
        return self.answer


class ChatService:
    """Singleton-style wrapper around the stateful Orchestrator."""

    _instance: "ChatService | None" = None

    def __new__(cls) -> "ChatService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._orch = Orchestrator()
        return cls._instance

    def chat(self, prompt: str, run_quality_check: bool = False) -> ChatResponse:
        result = self._orch.chat(prompt)
        return ChatResponse(
            answer=result.get("response", ""),
            tool_used=result.get("tool_used"),
            sources=result.get("sources", []),
            tool_result=result.get("tool_result"),
            metrics=result.get("metrics"),
        )

    def reset(self) -> None:
        self._orch.reset()
