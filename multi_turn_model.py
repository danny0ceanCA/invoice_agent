"""
Multi-turn conversation fusion model.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class ConversationState:
    original_query: Optional[str] = None
    latest_user_message: Optional[str] = None
    pending_intent: Optional[str] = None
    missing_slots: List[str] = field(default_factory=list)
    resolved_slots: Dict[str, str] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        return cls(
            original_query=data.get("original_query"),
            latest_user_message=data.get("latest_user_message"),
            pending_intent=data.get("pending_intent"),
            missing_slots=list(data.get("missing_slots", [])),
            resolved_slots=dict(data.get("resolved_slots", {})),
            history=list(data.get("history", [])),
        )


class MultiTurnConversationManager:
    def __init__(self, redis_client: "Redis", state_ttl_seconds: int = 86400) -> None:
        self.redis = redis_client
        self.state_ttl_seconds = state_ttl_seconds

    def _state_key(self, session_id: str) -> str:
        return f"session:{session_id}:state"

    def get_state(self, session_id: str) -> ConversationState:
        key = self._state_key(session_id)
        try:
            raw = self.redis.get(key)
        except Exception:
            raw = None
        if not raw:
            return ConversationState()
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            data = json.loads(raw)
            return ConversationState.from_dict(data)
        except Exception:
            return ConversationState()

    def save_state(self, state: ConversationState, session_id: Optional[str] = None) -> None:
        if session_id is None:
            if state.history:
                session_id = state.history[-1].get("session_id") or ""
            else:
                return
        key = self._state_key(session_id)
        try:
            payload = json.dumps(state.to_dict())
            try:
                self.redis.setex(key, self.state_ttl_seconds, payload)
            except Exception:
                self.redis.set(key, payload)
                try:
                    self.redis.expire(key, self.state_ttl_seconds)
                except Exception:
                    pass
        except Exception:
            pass

    def clear_state(self, session_id: str) -> None:
        key = self._state_key(session_id)
        try:
            self.redis.delete(key)
        except Exception:
            pass

    def process_user_message(
        self,
        session_id: str,
        user_message: str,
        required_slots: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        state = self.get_state(session_id)
        is_first_turn = state.original_query is None

        if is_first_turn:
            state.original_query = user_message
        else:
            state.latest_user_message = user_message

        state.history.append({"role": "user", "content": user_message})

        if required_slots is not None:
            current_missing = [slot for slot in required_slots if slot not in state.resolved_slots]
            state.missing_slots = current_missing

        self._attempt_slot_fill(state, user_message, allow_fallback_value=not is_first_turn)

        if required_slots is not None:
            state.missing_slots = [slot for slot in required_slots if slot not in state.resolved_slots]

        needs_clarification = bool(state.missing_slots)
        clarification_prompt = None
        if needs_clarification:
            slots_text = ", ".join(state.missing_slots)
            clarification_prompt = f"I need the following additional details: {slots_text}."

        fused_query = self.build_fused_query(state)

        self.save_state(state, session_id=session_id)

        return {
            "session_id": session_id,
            "needs_clarification": needs_clarification,
            "clarification_prompt": clarification_prompt,
            "fused_query": fused_query,
            "state": state.to_dict(),
        }

    def _attempt_slot_fill(
        self, state: ConversationState, user_message: str, *, allow_fallback_value: bool = True
    ) -> None:
        if not state.missing_slots:
            return

        normalized = user_message.strip()
        if not normalized:
            return

        lowered = normalized.lower()
        for slot in list(state.missing_slots):
            slot_key = slot.lower()
            prefix = f"{slot_key}:"
            if lowered.startswith(prefix):
                value = normalized[len(prefix):].strip()
                if value:
                    state.resolved_slots[slot] = value
                    state.missing_slots.remove(slot)
                return

        if allow_fallback_value and len(state.missing_slots) == 1 and len(normalized) <= 120 and "?" not in normalized:
            target_slot = state.missing_slots[0]
            state.resolved_slots[target_slot] = normalized
            state.missing_slots = []

    def build_fused_query(self, state: ConversationState) -> str:
        if not state.original_query:
            return state.latest_user_message or ""

        parts: List[str] = [state.original_query]

        if state.resolved_slots:
            details = "; ".join(f"{slot} is {value}" for slot, value in state.resolved_slots.items())
            parts.append(f"Details provided: {details}.")

        if state.latest_user_message and state.latest_user_message != state.original_query:
            if state.latest_user_message not in state.resolved_slots.values():
                parts.append(f"Additional instruction: {state.latest_user_message}.")

        return " ".join(part.strip() for part in parts if part).strip()


class FakeRedis:
    """In-memory Redis-like stub for testing."""

    def __init__(self) -> None:
        self.store: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    def set(self, key: str, value: str) -> None:
        self.store[key] = value

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    def expire(self, key: str, ttl: int) -> None:  # pragma: no cover - placeholder
        return None

    def delete(self, key: str) -> None:
        self.store.pop(key, None)


def demo() -> None:
    redis_client = FakeRedis()
    manager = MultiTurnConversationManager(redis_client)
    session_id = "demo-session"

    first_turn = manager.process_user_message(
        session_id,
        "Show me last month's performance report",
        required_slots=["department"],
    )
    second_turn = manager.process_user_message(
        session_id,
        "Marketing",
        required_slots=["department"],
    )

    print("First turn:", first_turn)
    print("Second turn:", second_turn)


if __name__ == "__main__":
    demo()
