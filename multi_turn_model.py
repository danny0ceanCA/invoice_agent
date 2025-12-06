"""
Unified, domain-agnostic multi-turn conversation manager.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog


LOGGER = structlog.get_logger(__name__)


def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Best-effort search for the project root that contains domain_config.json."""

    path = (start_path or Path(__file__)).resolve()
    for parent in [path] + list(path.parents):
        candidate = parent / "domain_config.json"
        if candidate.is_file():
            return parent
    return path.parent


def _load_domain_config() -> Dict[str, Any]:
    """Load domain_config.json safely, logging and returning an empty dict on failure."""

    try:
        root = find_project_root()
        config_path = root / "domain_config.json"
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("multi-turn-config load_failed", error=str(exc))
        return {}


DOMAIN_CONFIG: Dict[str, Any] = _load_domain_config()
MULTI_TURN_CONFIG: Dict[str, Any] = DOMAIN_CONFIG.get("multi_turn", {}) if DOMAIN_CONFIG else {}

if not MULTI_TURN_CONFIG:
    LOGGER.warning("multi-turn-config missing_or_empty")


def get_multi_turn_config() -> Dict[str, Any]:
    """Expose the loaded multi-turn configuration with a safe fallback."""

    return MULTI_TURN_CONFIG or {}


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
    last_session_id: Optional[str] = None
    active_mode: Optional[str] = None
    last_metric: Optional[str] = None
    last_plan_kind: Optional[str] = None

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
            last_session_id=data.get("last_session_id"),
            active_mode=data.get("active_mode"),
            last_metric=data.get("last_metric"),
            last_plan_kind=data.get("last_plan_kind"),
        )


class MultiTurnConversationManager:
    def __init__(
        self,
        redis_client: "Redis",
        state_ttl_seconds: int = 86400,
        multi_turn_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.redis = redis_client
        self.state_ttl_seconds = state_ttl_seconds
        self.multi_turn_config = multi_turn_config or get_multi_turn_config()

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
        state.last_session_id = session_id
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

    def _get_pattern_list(self, key: str, default: List[str]) -> List[str]:
        """Read a pattern list from config with a safe fallback."""

        patterns = self.multi_turn_config.get("patterns", {}) if self.multi_turn_config else {}
        return list(patterns.get(key, []) or default)

    def _get_topic_pattern_list(self, key: str, default: List[str]) -> List[str]:
        topic_patterns = (
            self.multi_turn_config.get("topic_patterns", {}) if self.multi_turn_config else {}
        )
        return list(topic_patterns.get(key, []) or default)

    def _get_name_stop_words(self) -> List[str]:
        default_stops = [
            "invoice",
            "vendor",
            "student",
            "cost",
            "amount",
            "total",
            "provider",
            "providers",
            "spend",
            "burn",
            "burn rate",
            "expenses",
            "charge",
            "charges",
            "health",
            "care",
            "hours",
            "school",
            "district",
            "all",
            "the",
            "and",
        ]
        return self._get_pattern_list("name_stop_words", default_stops)

    def _build_previous_slots(self, state: ConversationState) -> Dict[str, Optional[str]]:
        active_topic = state.active_topic if isinstance(state.active_topic, dict) else {}
        return {
            "entity_role": active_topic.get("type"),
            "entity_name": active_topic.get("value"),
            "metric": getattr(state, "last_metric", None),
            "mode": getattr(state, "active_mode", None),
            "plan_kind": getattr(state, "last_plan_kind", None),
            "time_window_kind": getattr(state, "last_period_type", None),
        }

    def _run_mti(self, state: ConversationState, user_message: str) -> Optional[dict]:
        """
        Call the Multi-Turn Intent (MTI) model to classify follow-ups.

        Returns a dict with keys:
          - decision: "fuse" | "new_topic" | "clarification"
          - reason: string
          - slots: { entity_role, entity_name, metric, mode, plan_kind, time_window_kind }
          - fused_query: string (best-effort)
        or None on failure.
        """

        config = self.multi_turn_config or {}
        if not config:
            LOGGER.debug("multi-turn-mti skipped: no config")
            return None

        previous_slots = self._build_previous_slots(state)
        try:
            slots_config = config.get("slots", {})
            decision_types = config.get("decision_types", {})
            patterns = config.get("patterns", {})
            topic_patterns = config.get("topic_patterns", {})
            period_handling = config.get("period_handling", {})
            defaults = config.get("defaults", {})

            prompt = (
                "You are a Multi-Turn Intent (MTI) classifier for a K-12 analytics agent. "
                "Use the configuration values to decide whether to fuse with the prior topic, start a new topic, "
                "or ask for clarification. Output JSON ONLY."
            )
            prompt += "\nCONFIG:\n"
            prompt += json.dumps(
                {
                    "slots": slots_config,
                    "decision_types": decision_types,
                    "patterns": patterns,
                    "topic_patterns": topic_patterns,
                    "period_handling": period_handling,
                    "defaults": defaults,
                },
                ensure_ascii=False,
                indent=2,
            )
            prompt += "\nPrevious slots: " + json.dumps(previous_slots, ensure_ascii=False)
            prompt += "\nUser message: " + user_message
            prompt += (
                "\nGuidelines:"
                "\n- Use only allowed values for metric, mode, plan_kind, and time_window_kind."
                "\n- If only the time window changes, prefer decision time_only_followup or fuse with updated time_window_kind."
                "\n- If asking about providers/hours for a student, consider provider_time_followup and set mode/plan_kind accordingly."
                "\n- If the entity changes, choose decision = 'new_topic'."
                "\n- If ambiguous, choose decision = 'clarification' and avoid assumptions."
                "\nRespond with JSON matching the schema: {decision, reason, slots, fused_query}."
            )

            LOGGER.debug(
                "multi-turn-mti prompt_prepared",
                previous_slots=previous_slots,
                prompt_preview=prompt[:500],
            )

            # Placeholder for actual MTI LLM call. When available, replace the stub below
            # with a structured LLM invocation and JSON parsing.
            # Example:
            # response = llm_client.generate(prompt)
            # decision = json.loads(response)
            # return decision
            return None
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("multi-turn-mti failed", error=str(exc))
            return None

    def _apply_mti_slots(
        self, state: ConversationState, slots: Dict[str, Any], fused_query: Optional[str]
    ) -> None:
        """Apply MTI slot values to the conversation state."""

        if not slots:
            return

        entity_role = slots.get("entity_role")
        entity_name = slots.get("entity_name")
        if entity_role and entity_name:
            state.active_topic = {
                "type": entity_role,
                "value": entity_name,
                "last_query": fused_query or (state.active_topic or {}).get("last_query"),
            }

        metric = slots.get("metric")
        if metric:
            state.last_metric = metric

        mode = slots.get("mode")
        if mode:
            state.active_mode = mode

        plan_kind = slots.get("plan_kind")
        if plan_kind:
            state.last_plan_kind = plan_kind

        time_window_kind = slots.get("time_window_kind")
        if time_window_kind:
            state.last_period_type = time_window_kind

    def _apply_mti_decision(
        self,
        decision: Dict[str, Any],
        state: ConversationState,
        session_id: str,
        user_message: str,
        required_slots: Optional[List[str]],
    ) -> Optional[Dict[str, Any]]:
        """Apply an MTI decision to the state and return a response payload."""

        if not decision:
            return None

        decision_type = decision.get("decision")
        slots = decision.get("slots") or {}
        fused_query = decision.get("fused_query") or user_message
        reason = decision.get("reason")

        if decision_type == "clarification":
            state.latest_user_message = user_message
            state.history.append({"role": "user", "content": user_message})
            clarification_prompt = reason or self._build_clarification_prompt(state)
            self.save_state(state, session_id=session_id)
            LOGGER.debug("multi-turn-mti clarification", reason=reason)
            return {
                "session_id": session_id,
                "needs_clarification": True,
                "clarification_prompt": clarification_prompt,
                "fused_query": None,
                "state": state.to_dict(),
            }

        if decision_type == "new_topic":
            self.clear_state(session_id)
            state = self._start_new_thread(user_message, required_slots)
            self._apply_mti_slots(state, slots, fused_query)
            state.original_query = fused_query
            state.latest_user_message = user_message
            state.history.append({"role": "user", "content": user_message})
            needs_clarification = bool(state.missing_slots)
            self.save_state(state, session_id=session_id)
            LOGGER.debug("multi-turn-mti new_topic", fused_query=fused_query)
            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(state)
                if needs_clarification
                else None,
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        if decision_type == "fuse":
            state.latest_user_message = user_message
            state.history.append({"role": "user", "content": user_message})
            self._apply_mti_slots(state, slots, fused_query)
            if state.active_topic:
                state.active_topic["last_query"] = fused_query
            if not state.original_query:
                state.original_query = fused_query
            needs_clarification = bool(state.missing_slots)
            self.save_state(state, session_id=session_id)
            LOGGER.debug("multi-turn-mti fused", fused_query=fused_query)
            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(state)
                if needs_clarification
                else None,
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        return None

    def process_user_message(
        self,
        session_id: str,
        user_message: str,
        required_slots: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if user_message.strip().lower() == "reset please":
            self.clear_state(session_id)
            print("[multi-turn] state cleared by user command", flush=True)
            state = ConversationState()
            fused_query = locals().get("fused_query")
            print("[multi-turn-debug] FUSION TRACE:")
            print(f"  - session_id: {session_id}")
            print(f"  - active_topic: {state.active_topic}")
            print(f"  - original_query: {state.original_query}")
            print(f"  - latest_user_message: {user_message}")
            print(f"  - fusion: {'YES' if fused_query else 'NO'}")
            print(f"  - fused_query: {fused_query or '<none>'}")
            return {
                "session_id": session_id,
                "needs_clarification": False,
                "clarification_prompt": None,
                "fused_query": "reset",
                "state": {},
            }

        user_message = user_message.strip()
        state = self.get_state(session_id)

        active_mode = getattr(state, "active_mode", None)
        last_query = None
        if isinstance(state.active_topic, dict):
            last_query = state.active_topic.get("last_query")
        if last_query is None:
            last_query = state.original_query

        mti_decision: Optional[Dict[str, Any]] = None
        if self.multi_turn_config:
            try:
                mti_decision = self._run_mti(state, user_message)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("multi-turn-mti invocation_failed", error=str(exc))

        if mti_decision:
            applied = self._apply_mti_decision(
                mti_decision, state, session_id, user_message, required_slots
            )
            if applied:
                fused_query = applied.get("fused_query")
                print("[multi-turn-debug] FUSION TRACE:")
                print(f"  - session_id: {session_id}")
                print(f"  - active_topic: {applied.get('state', {}).get('active_topic')}")
                print(f"  - original_query: {applied.get('state', {}).get('original_query')}")
                print(f"  - latest_user_message: {user_message}")
                print(f"  - fusion: {'YES' if fused_query else 'NO'}")
                print(f"  - fused_query: {fused_query or '<none>'}")
                return applied

        def _classify_mode(text: str) -> Optional[str]:
            t = text.lower()
            provider_terms = self._get_pattern_list(
                "provider_focus_phrases",
                [
                    "provider",
                    "providers",
                    "clinician",
                    "clinicians",
                    "care staff",
                    "nurse",
                    "lvn",
                    "hha",
                    "health aide",
                    "aide",
                ],
            )
            hours_terms = ["hours", "hrs"]
            if any(p in t for p in provider_terms) and any(h in t for h in hours_terms):
                return "student_provider_breakdown"

            total_terms = [
                "total cost",
                "total spend",
                "spend",
                "charges",
                "burn",
                "burn rate",
                "amount",
            ]
            if any(term in t for term in total_terms):
                return "student_total_cost"

            return None

        lower_message = user_message.lower()
        message_is_time_only = self._is_time_only(user_message)
        last_session_id = getattr(state, "last_session_id", None)
        active_topic = state.active_topic if isinstance(state.active_topic, dict) else {}
        active_topic_valid = active_topic.get("type") in {"student", "vendor", "district", "month"}
        time_only_followup = (
            message_is_time_only
            and last_session_id == session_id
            and active_topic_valid
            and state.original_query is not None
        )

        if message_is_time_only and not time_only_followup:
            return _reset_thread_and_return()

        # ============================================================
        # VISUAL FUSION LOG TREE
        # Prints a compact tree showing fusion details.
        # ============================================================
        def _log_fusion_tree(decision: str, reason: str, fused: str | None = None):
            try:
                LOGGER.debug("multi-turn-debug FUSION_DECISION_TREE")
                LOGGER.debug("└── FUSION_DECISION")
                LOGGER.debug(f"    ├── session_id: {session_id}")
                LOGGER.debug(f"    ├── active_topic: {active_topic}")
                LOGGER.debug(f"    ├── active_mode: {active_mode}")
                LOGGER.debug(f"    ├── last_query: {last_query}")
                LOGGER.debug(f"    ├── new_message: {user_message}")
                LOGGER.debug(f"    ├── decision: {decision}")
                LOGGER.debug(f"    ├── reason: {reason}")
                if fused:
                    LOGGER.debug(f"    └── fused_query: {fused}")
                else:
                    LOGGER.debug("    └── fused_query: <none>")
            except Exception:
                pass

        # ============================================================
        # PROVIDER FOLLOW-UP FUSION (Option B+)
        # Fuse with active student topic when:
        # - session_id matches
        # - active_topic.type == "student"
        # - follow-up mentions providers
        # - follow-up mentions time/month
        # - follow-up does NOT request district-wide scope
        # ============================================================

        if (
            session_id == getattr(state, "last_session_id", None)
            and active_topic
            and active_topic.get("type") == "student"
        ):

            text = user_message.lower().strip()

            provider_terms = self._get_pattern_list(
                "provider_focus_phrases",
                [
                    "provider",
                    "providers",
                    "clinician",
                    "clinicians",
                    "care staff",
                    "carestaff",
                    "nurse",
                    "lvn",
                    "hha",
                    "health aide",
                    "aide",
                    "who supported",
                    "who provided care",
                ],
            )

            time_terms = self._get_pattern_list(
                "time_shift_phrases",
                [
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
                    "this month",
                    "last month",
                    "this school year",
                    "this year",
                    "ytd",
                    "what about",
                    "now",
                    "next",
                    "then",
                ],
            )

            district_reset_terms = self._get_topic_pattern_list(
                "reset_triggers",
                ["district", "district-wide", "all students", "whole district"],
            )

            mentions_provider = any(term in text for term in provider_terms)
            mentions_time = any(term in text for term in time_terms)
            is_district_reset = any(term in text for term in district_reset_terms)

            if mentions_provider and mentions_time and not is_district_reset:
                previous_query = last_query or ""
                fused_query = f"{previous_query} Additional instruction: {user_message}"

                state.latest_user_message = user_message
                state.history.append({"role": "user", "content": user_message})
                state.active_mode = "student_provider_breakdown"
                active_topic["last_query"] = fused_query

                self.save_state(state, session_id=session_id)

                # DEBUG LOGS
                LOGGER.debug("multi-turn-debug PROVIDER_FUSION_TRIGGERED")
                LOGGER.debug("multi-turn-debug previous", previous=previous_query)
                LOGGER.debug("multi-turn-debug followup", followup=user_message)
                LOGGER.debug("multi-turn-debug fused_query", fused_query=fused_query)

                # Visual fusion log
                _log_fusion_tree(
                    decision="fused",
                    reason="provider_follow_up",
                    fused=fused_query,
                )

                fused_query = locals().get("fused_query")
                print("[multi-turn-debug] FUSION TRACE:")
                print(f"  - session_id: {session_id}")
                print(f"  - active_topic: {state.active_topic}")
                print(f"  - original_query: {state.original_query}")
                print(f"  - latest_user_message: {user_message}")
                print(f"  - fusion: {'YES' if fused_query else 'NO'}")
                print(f"  - fused_query: {fused_query or '<none>'}")
                return {
                    "session_id": session_id,
                    "needs_clarification": False,
                    "clarification_prompt": None,
                    "fused_query": fused_query,
                    "state": state.to_dict(),
                }

        if (
            session_id == getattr(state, "last_session_id", None)
            and active_topic
            and active_topic.get("type") == "student"
        ):
            t = user_message.lower().strip()

            time_only_terms = self._get_pattern_list(
                "time_shift_phrases",
                [
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
                    "this month",
                    "last month",
                    "this school year",
                    "this year",
                    "ytd",
                ],
            )
            is_time_only = any(m in t for m in time_only_terms) and "provider" not in t and "clinician" not in t

            if is_time_only and not any(dw in t for dw in ["district", "all students", "whole district"]):
                mode = active_mode or _classify_mode(last_query or "")

                if mode == "student_provider_breakdown":
                    fused_query = (
                        f"{last_query or ''} Time period is month focus is {user_message.strip()}. "
                        "Additional instruction: providers and hours for this month."
                    )
                else:
                    fused_query = (
                        f"{last_query or ''} Time period is month focus is {user_message.strip()}. "
                        f"Additional instruction: {user_message}"
                    )

                state.latest_user_message = user_message
                state.history.append({"role": "user", "content": user_message})
                state.active_mode = mode
                active_topic["last_query"] = fused_query
                self.save_state(state, session_id=session_id)

                _log_fusion_tree(
                    decision="fused",
                    reason="time_only_follow_up",
                    fused=fused_query,
                )

                fused_query = locals().get("fused_query")
                print("[multi-turn-debug] FUSION TRACE:")
                print(f"  - session_id: {session_id}")
                print(f"  - active_topic: {state.active_topic}")
                print(f"  - original_query: {state.original_query}")
                print(f"  - latest_user_message: {user_message}")
                print(f"  - fusion: {'YES' if fused_query else 'NO'}")
                print(f"  - fused_query: {fused_query or '<none>'}")
                return {
                    "session_id": session_id,
                    "needs_clarification": False,
                    "clarification_prompt": None,
                    "fused_query": fused_query,
                    "state": state.to_dict(),
                }

        def _reset_thread_and_return() -> Dict[str, Any]:
            print("[multi-turn-debug] SAFE_FUSION_RESET", flush=True)
            _log_fusion_tree(
                decision="reset",
                reason="does_not_meet_fusion_conditions",
                fused=None,
            )
            self.clear_state(session_id)
            fresh_state = self._start_new_thread(user_message, required_slots)
            fresh_state.active_mode = _classify_mode(user_message)

            extracted_name = self._extract_name(user_message)
            if extracted_name and self._is_valid_name(extracted_name):
                fresh_state.active_topic = {
                    "type": "student",
                    "value": extracted_name,
                    "last_query": user_message,
                }
            elif extracted_name and not self._is_valid_name(extracted_name):
                print(
                    f"[multi-turn-debug] IGNORE_BAD_NAME | extracted={extracted_name!r}",
                    flush=True,
                )

            needs_clarification = bool(fresh_state.missing_slots)
            fused_query = user_message
            print(f"[multi-turn] safe_new_thread: {user_message!r}", flush=True)
            self.save_state(fresh_state, session_id=session_id)
            fused_query = locals().get("fused_query")
            print("[multi-turn-debug] FUSION TRACE:")
            print(f"  - session_id: {session_id}")
            print(f"  - active_topic: {state.active_topic}")
            print(f"  - original_query: {state.original_query}")
            print(f"  - latest_user_message: {user_message}")
            print(f"  - fusion: {'YES' if fused_query else 'NO'}")
            print(f"  - fused_query: {fused_query or '<none>'}")
            return {
                "session_id": session_id,
                "needs_clarification": needs_clarification,
                "clarification_prompt": self._build_clarification_prompt(fresh_state)
                if needs_clarification
                else None,
                "fused_query": fused_query,
                "state": fresh_state.to_dict(),
            }

        new_intent_openers = self._get_topic_pattern_list(
            "new_intent_openers",
            [
                "i want",
                "give me",
                "show me",
                "list",
                "top",
                "highest",
                "summary",
                "most expensive",
                "all invoices",
                "what are",
                "what is",
                "vendor summary",
            ],
        )
        if any(lower_message.startswith(o) for o in new_intent_openers):
            return _reset_thread_and_return()

        extracted_name_new = self._extract_name(user_message)
        if extracted_name_new and self._is_valid_name(extracted_name_new):
            active_value = state.active_topic.get("value") if state.active_topic else None
            if not active_value or extracted_name_new.lower() != str(active_value).lower():
                return _reset_thread_and_return()

        district_terms = self._get_topic_pattern_list(
            "reset_triggers",
            ["district", "district-wide", "all invoices", "vendor summary"],
        )
        if any(term in lower_message for term in district_terms):
            return _reset_thread_and_return()

        last_mode = getattr(state, "last_mode", None)
        if last_mode == "invoice_details":
            summary_keywords = ["top", "highest", "summary", "total", "spend"]
            if any(keyword in lower_message for keyword in summary_keywords):
                return _reset_thread_and_return()

        has_active_topic = state.original_query is not None

        invoice_detail_followup = has_active_topic and any(
            term in lower_message
            for term in [
                "invoice detail",
                "invoice details",
                "line item",
                "line items",
                "drill down",
                "drilldown",
            ]
        )

        followup_markers = self._get_pattern_list(
            "followup_markers",
            [
                "now",
                "also",
                "what about",
                "continue",
                "next",
                "same",
                "and",
                "and for him",
                "and for her",
                "and for them",
            ],
        )
        if (
            not time_only_followup
            and not invoice_detail_followup
            and not any(marker in lower_message for marker in followup_markers)
        ):
            return _reset_thread_and_return()

        is_list_followup = (
            self._refers_to_prior_list(user_message, state) if has_active_topic else False
        )
        is_explicit_list = self._is_list_intent(user_message)

        if is_explicit_list and not is_list_followup:
            state = self._start_new_thread(user_message, required_slots)
            state.active_mode = _classify_mode(user_message)

            extracted_name = self._extract_name(user_message)
            if extracted_name and self._is_valid_name(extracted_name):
                state.active_topic = {
                    "type": "student",
                    "value": extracted_name,
                    "last_query": user_message,
                }
            elif extracted_name and not self._is_valid_name(extracted_name):
                print(
                    f"[multi-turn-debug] IGNORE_BAD_NAME | extracted={extracted_name!r}",
                    flush=True,
                )

            needs_clarification = bool(state.missing_slots)
            fused_query = user_message
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            print(
                f"[multi-turn-debug] NEW THREAD | msg={user_message!r} | active_topic={state.active_topic}",
                flush=True,
            )
            self.save_state(state, session_id=session_id)
            fused_query = locals().get("fused_query")
            print("[multi-turn-debug] FUSION TRACE:")
            print(f"  - session_id: {session_id}")
            print(f"  - active_topic: {state.active_topic}")
            print(f"  - original_query: {state.original_query}")
            print(f"  - latest_user_message: {user_message}")
            print(f"  - fusion: {'YES' if fused_query else 'NO'}")
            print(f"  - fused_query: {fused_query or '<none>'}")
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
            state.active_mode = _classify_mode(user_message)

            extracted_name = self._extract_name(user_message)
            if extracted_name and self._is_valid_name(extracted_name):
                state.active_topic = {
                    "type": "student",
                    "value": extracted_name,
                    "last_query": user_message,
                }
            elif extracted_name and not self._is_valid_name(extracted_name):
                print(
                    f"[multi-turn-debug] IGNORE_BAD_NAME | extracted={extracted_name!r}",
                    flush=True,
                )

            needs_clarification = bool(state.missing_slots)
            fused_query = self.build_fused_query(state)
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            print(
                f"[multi-turn-debug] NEW THREAD | msg={user_message!r} | active_topic={state.active_topic}",
                flush=True,
            )

            self.save_state(state, session_id=session_id)

            fused_query = locals().get("fused_query")
            print("[multi-turn-debug] FUSION TRACE:")
            print(f"  - session_id: {session_id}")
            print(f"  - active_topic: {state.active_topic}")
            print(f"  - original_query: {state.original_query}")
            print(f"  - latest_user_message: {user_message}")
            print(f"  - fusion: {'YES' if fused_query else 'NO'}")
            print(f"  - fused_query: {fused_query or '<none>'}")
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
            state.active_mode = _classify_mode(user_message)

            extracted_name = self._extract_name(user_message)
            if extracted_name and self._is_valid_name(extracted_name):
                state.active_topic = {
                    "type": "student",
                    "value": extracted_name,
                    "last_query": user_message,
                }
            elif extracted_name and not self._is_valid_name(extracted_name):
                print(
                    f"[multi-turn-debug] IGNORE_BAD_NAME | extracted={extracted_name!r}",
                    flush=True,
                )

            needs_clarification = bool(state.missing_slots)
            fused_query = self.build_fused_query(state)
            print(f"[multi-turn] new_thread: {user_message!r}", flush=True)
            print(
                f"[multi-turn-debug] NEW THREAD | msg={user_message!r} | active_topic={state.active_topic}",
                flush=True,
            )

            self.save_state(state, session_id=session_id)

            fused_query = locals().get("fused_query")
            print("[multi-turn-debug] FUSION TRACE:")
            print(f"  - session_id: {session_id}")
            print(f"  - active_topic: {state.active_topic}")
            print(f"  - original_query: {state.original_query}")
            print(f"  - latest_user_message: {user_message}")
            print(f"  - fusion: {'YES' if fused_query else 'NO'}")
            print(f"  - fused_query: {fused_query or '<none>'}")
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

        if message_is_time_only and time_only_followup:
            _log_fusion_tree(
                decision="fused",
                reason="time_only_follow_up",
                fused=fused_query,
            )

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

        fused_query = locals().get("fused_query")
        print("[multi-turn-debug] FUSION TRACE:")
        print(f"  - session_id: {session_id}")
        print(f"  - active_topic: {state.active_topic}")
        print(f"  - original_query: {state.original_query}")
        print(f"  - latest_user_message: {user_message}")
        print(f"  - fusion: {'YES' if fused_query else 'NO'}")
        print(f"  - fused_query: {fused_query or '<none>'}")
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

        explicit_phrases = self._get_pattern_list(
            "list_intent_phrases",
            [
                "student list",
                "list students",
                "list all students",
                "show students",
                "show student list",
                "show me student list",
                "show me the student list",
                "give me the student list",
                "provider list",
                "list providers",
                "list all providers",
                "show provider list",
                "show providers",
            ],
        )

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
        markers = self._get_pattern_list(
            "list_reference_phrases",
            [
                "that list",
                "this list",
                "the list you just showed",
                "the list you showed",
                "that provider list",
                "that student list",
            ],
        )
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

        i_want_markers = (
            "i want",
            "i need",
            "i would like",
            "i wanna",
        )

        if any(text.startswith(prefix) for prefix in i_want_markers):
            extracted_name = self._extract_name(message)
            if extracted_name:
                print("[multi-turn-debug] SUPPRESS_FOLLOWUP_I_WANT", flush=True)
                return False

        suppress_prefixes = [
            "i want",
            "i need",
            "i would like",
            "i'd like",
            "i wanna",
        ]
        starts_with_suppressed = any(text.startswith(prefix) for prefix in suppress_prefixes)
        markers = self._get_pattern_list(
            "followup_markers",
            [
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
            ],
        )
        marker_hit = any(marker in text for marker in markers)

        list_ref = False
        pronoun_prefix_hit = False
        school_year_hit = False
        month_hit = False
        if state.original_query:
            if "that list" in text or "this list" in text:
                list_ref = True

            pronoun_starts = self._get_pattern_list(
                "pronoun_followup_starters",
                [
                    "who has ",
                    "who provided ",
                    "who provides ",
                    "who did ",
                    "can you tell me who",
                    "why did it ",
                    "why did this ",
                    "why did that ",
                ],
            )
            if any(text.startswith(prefix) for prefix in pronoun_starts):
                pronoun_prefix_hit = True

            if "school year" in text or "this school year" in text:
                school_year_hit = True

            if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", text):
                month_hit = True

        is_followup = marker_hit or list_ref or pronoun_prefix_hit or school_year_hit or month_hit

        if starts_with_suppressed and not (list_ref or pronoun_prefix_hit or school_year_hit or month_hit):
            print("[multi-turn-debug] SUPPRESS_FOLLOWUP_I_WANT", flush=True)
            return False

        return is_followup

    def _is_followup_message(self, message: str) -> bool:
        if not message:
            return False
        text = message.lower().strip()
        start_markers = self._get_pattern_list(
            "followup_markers",
            [
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
            ],
        )
        if any(text.startswith(marker) for marker in start_markers):
            return True

        month_pattern = r"^(january|february|march|april|may|june|july|august|september|october|november|december)\b[\w\s]*\??$"
        if re.search(month_pattern, text):
            return True

        if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", text):
            return True

        return False

    def _is_time_only(self, message: str) -> bool:
        if not message:
            return False

        normalized = re.sub(r"[?.!]", "", message.strip().lower())
        if not normalized:
            return False

        if normalized.startswith("what about "):
            normalized = normalized[len("what about ") :].strip()
        if normalized.startswith("now "):
            normalized = normalized[len("now ") :].strip()

        time_phrases = set(
            self._get_pattern_list(
                "time_shift_phrases",
                [
                    "this school year",
                    "current school year",
                    "this month",
                    "last month",
                    "this year",
                    "last year",
                    "this sy",
                ],
            )
        )

        if normalized in time_phrases:
            return True

        month_pattern = (
            r"^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
            r"aug(?:ust)?|sep(?:t)?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?$"
        )

        return bool(re.match(month_pattern, normalized))

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
        if not message:
            return None

        configured_stops = set(self._get_name_stop_words())
        stop_words = configured_stops.union(
            {
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
                "Provider",
                "Providers",
                "Student",
                "Students",
                "Cost",
                "Hours",
                "Service",
                "Services",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
            }
        )
        stop_words_lower = {word.lower() for word in stop_words}

        token_pattern = r"\b[A-Z][a-z]+\b"

        for_match_iter = re.finditer(r"\bfor\s+((?:[A-Z][a-z]+(?:\s+|$)){1,2})", message)
        for match in for_match_iter:
            tokens = re.findall(token_pattern, match.group(1))
            if not 1 <= len(tokens) <= 2:
                candidate = " ".join(tokens) if tokens else match.group(1).strip()
                print(f"[multi-turn-debug] NAME_SKIPPED: {candidate!r}", flush=True)
                continue
            if any(token.lower() in stop_words_lower for token in tokens):
                candidate = " ".join(tokens)
                print(f"[multi-turn-debug] NAME_SKIPPED: {candidate!r}", flush=True)
                continue
            candidate = " ".join(tokens)
            print(f"[multi-turn-debug] NAME_EXTRACTED: {candidate!r}", flush=True)
            return candidate

        name_seq_pattern = r"\b[A-Z][a-z]+\b(?:\s+\b[A-Z][a-z]+\b)?"
        for match in re.finditer(name_seq_pattern, message):
            tokens = re.findall(token_pattern, match.group(0))
            if not 1 <= len(tokens) <= 2:
                candidate = " ".join(tokens) if tokens else match.group(0).strip()
                print(f"[multi-turn-debug] NAME_SKIPPED: {candidate!r}", flush=True)
                continue
            if any(token.lower() in stop_words_lower for token in tokens):
                candidate = " ".join(tokens)
                print(f"[multi-turn-debug] NAME_SKIPPED: {candidate!r}", flush=True)
                continue
            candidate = " ".join(tokens)
            print(f"[multi-turn-debug] NAME_EXTRACTED: {candidate!r}", flush=True)
            return candidate

        return None

    def _is_valid_name(self, name: str) -> bool:
        if not name:
            return False
        bad = set(word.lower() for word in self._get_name_stop_words())
        bad.update(
            {
                "i",
                "me",
                "you",
                "we",
                "they",
                "i want",
                "want",
                "show",
                "give",
                "this",
                "that",
                "it",
                "cost",
                "hours",
                "provider",
                "providers",
                "student",
                "students",
                "see",
            }
        )
        return name.lower() not in bad

    def _refers_to_provider_followup(self, message: str, state: ConversationState) -> bool:
        if not state.active_topic or state.active_topic.get("type") != "student":
            return False

        text = (message or "").lower()
        provider_keywords = self._get_pattern_list(
            "provider_focus_phrases",
            [
                "provider",
                "providers",
                "hours",
                "care",
                "who provided",
                "show me providers",
            ],
        )

        if not any(keyword in text for keyword in provider_keywords):
            return False

        extracted_name = self._extract_name(message)
        if extracted_name and self._is_valid_name(extracted_name):
            active_student = state.active_topic.get("value")
            if not active_student or extracted_name.lower() != str(active_student).lower():
                return False

        print("[multi-turn-debug] PROVIDER_FOLLOWUP_MATCH", flush=True)
        return True

    def _starts_new_topic(self, message: str, state: ConversationState) -> bool:
        if state.original_query is None:
            return True

        if self._refers_to_provider_followup(message, state):
            print("[multi-turn-debug] PROVIDER_FOLLOWUP_SUPPRESS_TOPIC_SHIFT", flush=True)
            return False

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
