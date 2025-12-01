"""
Unified, domain-agnostic multi-turn conversation manager.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
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
        user_message = user_message.strip()
        state = self.get_state(session_id)

        if self._is_list_intent(user_message):
            state = self._start_new_thread(user_message, required_slots)
            needs_clarification = False
            fused_query = user_message
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            self.save_state(state, session_id=session_id)
            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": None,
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        if state.original_query is None:
            state = self._start_new_thread(user_message, required_slots)
            needs_clarification = bool(state.missing_slots)
            fused_query = user_message
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            self.save_state(state, session_id=session_id)
            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(state),
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        if self._starts_new_topic(user_message, state):
            state = self._start_new_thread(user_message, required_slots)
            needs_clarification = bool(state.missing_slots)
            fused_query = user_message
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            self.save_state(state, session_id=session_id)
            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(state),
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        # Follow-up message keeps the existing thread
        state.history.append({"role": "user", "content": user_message})
        state.latest_user_message = user_message

        if required_slots is not None and not state.missing_slots:
            state.missing_slots = list(required_slots)

        self._attempt_slot_fill(state, user_message, allow_fallback_value=True)

        needs_clarification = bool(state.missing_slots)
        fused_query = self.build_fused_query(state)
        print(f"[multi-turn] followup_fused: {fused_query!r}", flush=True)

        self.save_state(state, session_id=session_id)

        return {
            "session_id": session_id,
            "needs_clarification": needs_clarification,
            "clarification_prompt": self._build_clarification_prompt(state) if needs_clarification else None,
            "fused_query": fused_query,
            "state": state.to_dict(),
        }

    def _start_new_thread(
        self, user_message: str, required_slots: Optional[List[str]]
    ) -> ConversationState:
        missing_slots = list(required_slots) if required_slots else []
        return ConversationState(
            original_query=user_message,
            latest_user_message=user_message,
            pending_intent=None,
            missing_slots=missing_slots,
            resolved_slots={},
            history=[{"role": "user", "content": user_message}],
        )

    def _is_list_intent(self, query: str) -> bool:
        if not query:
            return False
        text = query.lower().strip()
        list_patterns = [
            r"\blist\s+of\s+\w+",
            r"\b\w+\s+list\b",
            r"\blist\s+\w+",
            r"\bshow\s+.*\blist\b",
        ]
        phrases = [
            "list of",
            "list all",
            "show me the list",
        ]
        if any(phrase in text for phrase in phrases):
            return True
        return any(re.search(pattern, text) for pattern in list_patterns)

    def _is_followup(self, message: str) -> bool:
        if not message:
            return False
        text = message.lower()
        markers = [
            "now",
            "also",
            "again",
            "too",
            "as well",
            "another",
            "next",
            "what about",
            "how about",
            "same",
            "continue",
        ]
        return any(marker in text for marker in markers)

    def _starts_new_topic(self, message: str, state: ConversationState) -> bool:
        if not state.original_query:
            return False
        lowered = message.lower().strip()
        if self._mentions_new_entity(lowered):
            return True
        if self._is_followup(lowered):
            return False
        if self._looks_like_short_clarification(lowered):
            return False
        triggers = [
            "show",
            "give me",
            "what is",
            "how many",
            "tell me",
            "provide",
            "find",
        ]
        if any(lowered.startswith(trigger) for trigger in triggers):
            return True
        return True

    def _mentions_new_entity(self, message: str) -> bool:
        if not message:
            return False
        return bool(re.search(r"\bfor\s+\w+", message))

    def _looks_like_short_clarification(self, message: str) -> bool:
        if not message:
            return False
        short_replies = {"yes", "no", "ok", "okay", "correct", "right", "sure", "thanks"}
        words = message.split()
        if len(words) <= 4:
            return True
        if message in short_replies:
            return True
        return False

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
            pattern = rf"{re.escape(slot_key)}\s*[:=-]\s*(.+)"
            match = re.search(pattern, lowered)
            if match:
                value = normalized[match.start(1) : match.end(1)].strip()
                if value:
                    state.resolved_slots[slot] = value
                    state.missing_slots.remove(slot)
                continue

        if allow_fallback_value and len(state.missing_slots) == 1 and len(normalized) <= 120 and "?" not in normalized:
            target_slot = state.missing_slots[0]
            state.resolved_slots[target_slot] = normalized
            state.missing_slots = []

    def _build_clarification_prompt(self, state: ConversationState) -> Optional[str]:
        if not state.missing_slots:
            return None
        slots_text = ", ".join(state.missing_slots)
        return f"I need the following additional details: {slots_text}."

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
        "Show me the latest metrics",
        required_slots=["category"],
    )
    second_turn = manager.process_user_message(
        session_id,
        "category: web traffic",
        required_slots=["category"],
    )

    print("First turn:", first_turn)
    print("Second turn:", second_turn)


if __name__ == "__main__":
    demo()
