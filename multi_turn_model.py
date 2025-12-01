"""
Unified, domain-agnostic multi-turn conversation manager.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass
class ConversationState:
    original_query: Optional[str] = None
    latest_user_message: Optional[str] = None
    pending_intent: Optional[str] = None
    missing_slots: List[str] = field(default_factory=list)
    resolved_slots: Dict[str, str] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    active_topic: Dict[str, Any] = field(default_factory=dict)
    last_period_type: Optional[str] = None
    last_period_start: Optional[str] = None
    last_period_end: Optional[str] = None
    last_month: Optional[str] = None
    last_year_window: Optional[str] = None

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
            active_topic=dict(data.get("active_topic", {})),
            last_period_type=data.get("last_period_type"),
            last_period_start=data.get("last_period_start"),
            last_period_end=data.get("last_period_end"),
            last_month=data.get("last_month"),
            last_year_window=data.get("last_year_window"),
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

        has_active_topic = state.original_query is not None
        is_list_followup = (
            self._refers_to_prior_list(user_message, state) if has_active_topic else False
        )
        is_explicit_list = self._is_list_intent(user_message)

        if is_explicit_list and not is_list_followup:
            state = self._start_new_thread(user_message, required_slots)

            extracted_name = self._extract_name(user_message)
            if extracted_name:
                state.active_topic = {
                    "type": "student",
                    "value": extracted_name,
                    "last_query": user_message,
                }

            needs_clarification = bool(state.missing_slots)
            fused_query = user_message
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            print(
                f"[multi-turn-debug] NEW THREAD | msg={user_message!r} | active_topic={state.active_topic}",
                flush=True,
            )
            self.save_state(state, session_id=session_id)
            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(state)
                if needs_clarification
                else None,
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        if not has_active_topic:
            state = self._start_new_thread(user_message, required_slots)

            extracted_name = self._extract_name(user_message)
            if extracted_name:
                state.active_topic = {
                    "type": "student",
                    "value": extracted_name,
                    "last_query": user_message,
                }

            needs_clarification = bool(state.missing_slots)
            fused_query = self.build_fused_query(state)
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            print(
                f"[multi-turn-debug] NEW THREAD | msg={user_message!r} | active_topic={state.active_topic}",
                flush=True,
            )

            self.save_state(state, session_id=session_id)

            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(state)
                if needs_clarification
                else None,
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        is_short_wh_followup = (
            self._is_short_wh_followup(user_message) if has_active_topic else False
        )

        starts_new_topic = self._starts_new_topic(user_message, state)

        if starts_new_topic and not is_list_followup and not is_short_wh_followup:
            state = self._start_new_thread(user_message, required_slots)

            extracted_name = self._extract_name(user_message)
            if extracted_name:
                state.active_topic = {
                    "type": "student",
                    "value": extracted_name,
                    "last_query": user_message,
                }

            needs_clarification = bool(state.missing_slots)
            fused_query = self.build_fused_query(state)
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            print(
                f"[multi-turn-debug] NEW THREAD | msg={user_message!r} | active_topic={state.active_topic}",
                flush=True,
            )

            self.save_state(state, session_id=session_id)

            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(state)
                if needs_clarification
                else None,
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        # Follow-up message keeps the existing thread
        state.history.append({"role": "user", "content": user_message})
        state.latest_user_message = user_message

        period_info = self._extract_period_info(user_message)
        is_followup = self._is_followup_message(user_message)
        lower_message = user_message.lower()

        if period_info.get("has_explicit_period"):
            for field_name in [
                "last_period_type",
                "last_period_start",
                "last_period_end",
                "last_month",
                "last_year_window",
            ]:
                setattr(state, field_name, None)

        if (
            is_followup
            and not period_info.get("has_explicit_period")
            and "district wide" not in lower_message
        ):
            for field_name in [
                "last_period_type",
                "last_period_start",
                "last_period_end",
                "last_month",
                "last_year_window",
            ]:
                if period_info.get(field_name) is None:
                    period_info[field_name] = getattr(state, field_name)

        for field_name in [
            "last_period_type",
            "last_period_start",
            "last_period_end",
            "last_month",
            "last_year_window",
        ]:
            if field_name in period_info and period_info[field_name] is not None:
                setattr(state, field_name, period_info[field_name])

        if required_slots is not None and not state.missing_slots:
            state.missing_slots = list(required_slots)

        self._attempt_slot_fill(state, user_message, allow_fallback_value=True)

        needs_clarification = bool(state.missing_slots)
        fused_query = self.build_fused_query(state)
        extracted_name = self._extract_name(user_message)

        if is_short_wh_followup:
            print(f"[multi-turn] followup_short_wh: {fused_query!r}", flush=True)
        else:
            print(f"[multi-turn] followup_fused: {fused_query!r}", flush=True)

            print(
                f"[multi-turn-debug] FOLLOWUP | msg={user_message!r} | active_topic={state.active_topic} | period=({state.last_period_start} → {state.last_period_end}) | month={state.last_month}",
                flush=True,
            )

        if not state.active_topic and extracted_name:
            state.active_topic = {
                "type": "student",
                "value": extracted_name,
                "last_query": user_message,
            }

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
        period_info = self._extract_period_info(user_message)
        return ConversationState(
            original_query=user_message,
            latest_user_message=user_message,
            pending_intent=None,
            missing_slots=missing_slots,
            resolved_slots={},
            history=[{"role": "user", "content": user_message}],
            active_topic={},
            last_period_type=period_info.get("last_period_type"),
            last_period_start=period_info.get("last_period_start"),
            last_period_end=period_info.get("last_period_end"),
            last_month=period_info.get("last_month"),
            last_year_window=period_info.get("last_year_window"),
        )

    def _is_list_intent(self, query: str) -> bool:
        if not query:
            return False
        text = query.lower().strip()

        explicit_phrases = [
            "student list",
            "list students",
            "list all students",
            "show students",
            "show me the student list",
            "give me the student list",
            "provider list",
            "list providers",
            "list all providers",
            "show provider list",
            "show providers",
        ]

        for phrase in explicit_phrases:
            if (
                text == phrase
                or text.startswith(f"{phrase} ")
                or text.startswith(f"{phrase}?")
                or text.startswith(f"{phrase}.")
            ):
                return True

        return False

    def _refers_to_prior_list(self, message: str, state: ConversationState) -> bool:
        if not message or not state.original_query:
            return False
        text = message.lower().strip()
        markers = [
            "that list",
            "this list",
            "the list you just showed",
            "the list you showed",
            "that provider list",
            "that student list",
        ]
        return any(marker in text for marker in markers)

    def _is_short_wh_followup(self, message: str) -> bool:
        if not message:
            return False

        normalized = message.strip()
        if len(normalized) > 80:
            return False

        prefixes = [
            "who",
            "what",
            "why",
            "how",
            "when",
            "where",
            "can you",
            "could you",
            "would you",
            "now",
            "ok",
            "okay",
            "and",
            "then",
        ]

        lower_message = normalized.lower()
        if not any(lower_message.startswith(prefix) for prefix in prefixes):
            return False

        capitalized_words = re.findall(r"\b[A-Z][a-z]+\b", normalized)
        if len(capitalized_words) >= 2:
            return False

        return True

    def _is_followup(self, message: str, state: ConversationState) -> bool:
        if not message:
            return False
        text = message.lower().strip()
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
        if any(marker in text for marker in markers):
            return True

        if state.original_query:
            if "that list" in text or "this list" in text:
                return True

            pronoun_starts = [
                "who has ",
                "who provided ",
                "who provides ",
                "who did ",
                "can you tell me who",
                "why did it ",
                "why did this ",
                "why did that ",
            ]
            if any(text.startswith(prefix) for prefix in pronoun_starts):
                return True

            if "school year" in text or "this school year" in text:
                return True

            if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", text):
                return True

        return False

    def _is_followup_message(self, message: str) -> bool:
        if not message:
            return False
        text = message.lower().strip()
        start_markers = [
            "why",
            "what about",
            "how about",
            "now",
            "next",
            "and",
            "also",
            "continue",
            "then",
            "same",
        ]
        if any(text.startswith(marker) for marker in start_markers):
            return True

        month_pattern = r"^(january|february|march|april|may|june|july|august|september|october|november|december)\b[\w\s]*\??$"
        if re.search(month_pattern, text):
            return True

        if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", text):
            return True

        return False

    def _extract_period_info(self, message: str) -> Dict[str, Optional[str]]:
        info: Dict[str, Optional[str]] = {
            "last_period_type": None,
            "last_period_start": None,
            "last_period_end": None,
            "last_month": None,
            "last_year_window": None,
            "has_explicit_period": False,
        }

        if not message:
            return info

        text = message.lower()
        info["has_explicit_period"] = bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", text))

        today = date.today()
        month_names = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]

        month_match = re.search(
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+(\d{4}))?",
            text,
        )
        if month_match:
            month_name = month_match.group(1).title()
            if month_match.group(2):
                month_name = f"{month_name} {month_match.group(2)}"
            info["last_month"] = month_name

        if "ytd" in text or "year to date" in text:
            start_year = today.year if today.month >= 7 else today.year - 1
            info["last_period_type"] = "school_year"
            info["last_period_start"] = date(start_year, 7, 1).isoformat()
            info["last_period_end"] = today.isoformat()
            info["last_year_window"] = "school year to date"
            return info

        if "this year" in text or "school year" in text:
            start_year = today.year if today.month >= 7 else today.year - 1
            info["last_period_type"] = "school_year"
            info["last_period_start"] = date(start_year, 7, 1).isoformat()
            info["last_period_end"] = date(start_year + 1, 6, 30).isoformat()
            info["last_year_window"] = "this school year"
            return info

        if any(month in text for month in month_names) and info["last_month"]:
            info["last_period_type"] = "month"

        return info

    def _extract_name(self, message: str) -> Optional[str]:
        """
        Heuristic student-name extractor.

        Rules:
        - Prefer patterns like "for Carter Sanchez", "for Chloe Taylor".
        - Ignore obvious non-names (I, This, That, Can, months, etc.).
        - Fall back to capitalized tokens as a name (supports single-word names like "Luke").
        """
        if not message:
            return None

        # 1) Prefer "for First Last" style patterns (e.g., "for Carter Sanchez").
        #    Requires at least two capitalized words so we don't grab "for July".
        for_pattern = re.search(
            r"\bfor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",
            message,
        )
        if for_pattern:
            return for_pattern.group(1).strip()

        # 2) Fallback: scan for capitalized tokens that look like names
        #    and ignore pronouns, months, and common verbs.
        tokens = re.findall(r"\b[A-Z][a-z]+\b", message)

        stop_words = {
            "I",
            "We",
            "You",
            "They",
            "It",
            "This",
            "That",
            "Now",
            "Then",
            "Can",
            "Give",
            "Show",
            "List",
            "Who",
            "What",
            "Why",
            "How",
            "When",
            "Where",
            # months – we don't want "July August" as a name
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        }

        name_tokens = [t for t in tokens if t not in stop_words]

        # Prefer "First Last" if we have at least two name-like tokens
        if len(name_tokens) >= 2:
            return f"{name_tokens[0]} {name_tokens[1]}"

        # Otherwise, a single remaining capitalized token is probably a first name
        if len(name_tokens) == 1:
            return name_tokens[0]

        return None

    def _starts_new_topic(self, message: str, state: ConversationState) -> bool:
        if state.original_query is None:
            return True

        text = message.lower().strip()

        # --- 1) ENTITY-BASED TOPIC SHIFT (student change) --------------------
        new_name = self._extract_name(message)
        old_name = self._extract_name(state.original_query or "")

        if new_name and old_name and new_name.lower() != old_name.lower():
            # New explicit student → always a new topic
            print(
                f"[multi-turn-debug] NEW_TOPIC_BY_STUDENT | old={old_name!r} -> new={new_name!r}",
                flush=True,
            )
            return True

        if new_name and not old_name:
            # Previously no student, now we have one → new topic
            print(
                f"[multi-turn-debug] NEW_TOPIC_BY_STUDENT | old=None -> new={new_name!r}",
                flush=True,
            )
            return True

        if new_name and text == new_name.lower():
            # Message is just the name (e.g., "Carter Sanchez") → treat as a fresh topic
            print(
                f"[multi-turn-debug] NEW_TOPIC_BY_NAME_ONLY | name={new_name!r}",
                flush=True,
            )
            return True

        # --- 2) POINTERS BACK TO PRIOR LISTS ARE FOLLOW-UPS -----------------
        if self._refers_to_prior_list(message, state):
            return False

        # --- 3) PURE FOLLOW-UP MARKERS (what about, now, this school year...) ---
        # These only apply if we did NOT detect a new student.
        if self._is_followup(message, state):
            return False

        # --- 4) EXPLICIT LIST INTENTS (global) ------------------------------
        if self._is_list_intent(text):
            return True

        return False

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
        base_query = state.original_query or (
            state.active_topic.get("last_query") if state.active_topic else None
        )
        if not base_query:
            return state.latest_user_message or ""

        parts: List[str] = [base_query]

        if state.resolved_slots:
            details = "; ".join(f"{slot} is {value}" for slot, value in state.resolved_slots.items())
            parts.append(f"Details provided: {details}.")

        period_details: List[str] = []
        if state.last_year_window:
            period_details.append(state.last_year_window)
        if state.last_period_start and state.last_period_end:
            period_details.append(f"{state.last_period_start} to {state.last_period_end}")
        elif state.last_period_start:
            period_details.append(f"starting {state.last_period_start}")
        if state.last_month:
            period_details.append(f"month focus is {state.last_month}")

        if period_details:
            parts.append(f"Time period is {'; '.join(period_details)}.")

        if state.latest_user_message and state.latest_user_message != state.original_query:
            if state.latest_user_message not in state.resolved_slots.values():
                parts.append(f"Additional instruction: {state.latest_user_message}")

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
