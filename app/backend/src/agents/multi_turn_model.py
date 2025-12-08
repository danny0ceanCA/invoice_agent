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

CONFIG_PATH = Path(__file__).parent / "domain_config.json"


def _load_domain_config() -> Dict[str, Any]:
    """Load domain_config.json safely, logging and returning an empty dict on failure."""

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            multi_turn = data.get("multi_turn", {}) if isinstance(data, dict) else {}
            if multi_turn:
                multi_turn.setdefault("patterns", {})
                multi_turn.setdefault("decision_types", {})
                multi_turn.setdefault("defaults", {})
                multi_turn.setdefault("examples", [])
            return data
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
    candidate_entities: List[str] = field(default_factory=list)
    last_invoice_candidates: List[str] = field(default_factory=list)
    last_period_type: Optional[str] = None
    last_period_start: Optional[str] = None
    last_period_end: Optional[str] = None
    last_month: Optional[str] = None
    last_explicit_month: Optional[str] = None
    last_year_window: Optional[str] = None
    last_session_id: Optional[str] = None
    active_mode: Optional[str] = None
    last_metric: Optional[str] = None
    last_plan_kind: Optional[str] = None
    last_intent_shape: Optional[str] = None

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
            candidate_entities=list(data.get("candidate_entities", [])),
            last_invoice_candidates=list(data.get("last_invoice_candidates", [])),
            last_period_type=data.get("last_period_type"),
            last_period_start=data.get("last_period_start"),
            last_period_end=data.get("last_period_end"),
            last_month=data.get("last_month"),
            last_explicit_month=data.get("last_explicit_month"),
            last_year_window=data.get("last_year_window"),
            last_session_id=data.get("last_session_id"),
            active_mode=data.get("active_mode"),
            last_metric=data.get("last_metric"),
            last_plan_kind=data.get("last_plan_kind"),
            last_intent_shape=data.get("last_intent_shape"),
        )


class MultiTurnConversationManager:
    METRIC_PLAN_MAP = {
        ("student", "cost"): "student_monthly_spend",
        ("student", "hours"): "student_monthly_hours",
        ("student", "caseload"): "caseload",
        ("vendor", "cost"): "vendor_monthly_spend",
        ("district", "cost"): "district_monthly_spend",
        ("clinician", "caseload"): "caseload",
        ("clinician", "hours"): "provider_daily_hours",
    }

    def __init__(
        self,
        redis_client: "Redis",
        state_ttl_seconds: int = 86400,
        multi_turn_config: Optional[Dict[str, Any]] = None,
        llm_client: "OpenAI" | None = None,
        llm_model: str | None = None,
    ) -> None:
        self.redis = redis_client
        self.state_ttl_seconds = state_ttl_seconds
        self.multi_turn_config = multi_turn_config or get_multi_turn_config()
        self.llm_client = llm_client
        self.llm_model = llm_model

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

    def update_last_plan_kind(self, session_id: str, plan_kind: Optional[str]) -> None:
        if not plan_kind:
            return
        state = self.get_state(session_id)
        state.last_plan_kind = plan_kind
        self.save_state(state, session_id=session_id)

    def _get_pattern_list(
        self, key: str, default: Optional[List[str]] = None
    ) -> List[str]:
        """Read a pattern list from config with a safe fallback."""

        patterns = self.multi_turn_config.get("patterns", {}) if self.multi_turn_config else {}
        topic_patterns = (
            self.multi_turn_config.get("topic_patterns", {}) if self.multi_turn_config else {}
        )
        default = default or []
        value = patterns.get(key, default)
        if not value and key in topic_patterns:
            value = topic_patterns.get(key, default)
        if isinstance(value, dict):
            return value  # type: ignore[return-value]
        return list(value or default)

    def _get_topic_pattern_list(
        self, key: str, default: Optional[List[str]] = None
    ) -> List[str]:
        topic_patterns = (
            self.multi_turn_config.get("topic_patterns", {}) if self.multi_turn_config else {}
        )
        default = default or []
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

    def _should_reset_topic(self, user_message: str, state: ConversationState) -> bool:
        """
        More conservative reset logic:
        Only reset the topic when:
        - user explicitly uses reset triggers
        - entity name appears that is DIFFERENT from active_topic
        - user explicitly uses new intent openers AND the message contains a NEW entity
        """
        msg = user_message.lower()

        # explicit resets
        for trig in self._get_topic_pattern_list("reset_triggers"):
            if trig in msg:
                return True

        # if no active topic, cannot reset
        if not state.active_topic:
            return False

        active_name = state.active_topic.get("value", "").lower()

        # detect if user mentions a different name → new topic
        for name in state.candidate_entities:
            if name.lower() != active_name and name.lower() in msg:
                return True

        # detect "new intent openers" only if a new entity is referenced
        for opener in self._get_topic_pattern_list("new_intent_openers"):
            if msg.startswith(opener):
                # opener alone doesn't reset — only reset if new entity appears
                for name in state.candidate_entities:
                    if name.lower() != active_name and name.lower() in msg:
                        return True

        return False

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

    def _merge_slots(
        self,
        previous: Dict[str, Optional[str]],
        current: Dict[str, Optional[str]],
        reset_keys: Optional[List[str]] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Merge two slot dictionaries with clear precedence.

        - ``current`` values always take precedence when provided.
        - ``previous`` values fill in only when ``current`` is missing.
        - Keys listed in ``reset_keys`` are forced to ``None``.
        """

        result: Dict[str, Optional[str]] = {}
        reset_keys = reset_keys or []
        all_keys = set(previous.keys()) | set(current.keys()) | set(reset_keys)

        for key in all_keys:
            if key in reset_keys:
                result[key] = None
                continue

            current_value = current.get(key)
            previous_value = previous.get(key)

            if current_value is not None:
                result[key] = current_value
                continue

            if previous_value is not None:
                result[key] = previous_value
            else:
                result[key] = None

        return result

    def _fallback_decision(self, user_message: str) -> Optional[str]:
        """
        Only fallback when MTI *clearly* cannot classify something
        AND the message looks like a single-turn new query.

        This greatly reduces SAFE_FUSION_RESET.
        """
        msg = user_message.strip().lower()

        # If it's a list intent → never fallback
        if any(phrase in msg for phrase in self._get_pattern_list("list_intent_phrases")):
            return None

        # If it's a pure time follow-up → MTI should handle, not fallback
        if any(phrase in msg for phrase in self._get_pattern_list("time_shift_phrases")):
            return None

        # If it looks like a new standalone query
        for opener in self._get_topic_pattern_list("new_intent_openers"):
            if msg.startswith(opener):
                return "new_topic"

        # otherwise, do not fallback
        return None

    def _infer_intent_shape(self, text: str) -> str:
        """
        Returns a coarse analytic intent category for fusion decisions:
        Possible return values:
            "student_metrics"
            "provider_breakdown"
            "district_metrics"
            "invoice_details"
            "list_entities"
            "unknown"
        Use simple keyword heuristics only.
        Must NOT import domain_config or planner/router modules.
        """

        msg = (text or "").lower()
        if not msg:
            return "unknown"

        provider_terms = ["provider", "providers", "clinician", "clinicians", "nurse", "nurses"]
        if any(term in msg for term in provider_terms):
            return "provider_breakdown"

        district_terms = ["district", "district-wide", "district wide", "across district"]
        if any(term in msg for term in district_terms):
            return "district_metrics"

        invoice_terms = ["invoice", "invoice number", "line items", "line item"]
        if any(term in msg for term in invoice_terms):
            return "invoice_details"

        list_terms = ["list", "show students", "show student list", "show clinicians", "show providers"]
        if any(term in msg for term in list_terms):
            return "list_entities"

        cost_terms = ["cost", "spend", "hours", "hour", "monthly"]
        if any(term in msg for term in cost_terms) and not any(
            term in msg for term in provider_terms
        ):
            return "student_metrics"

        return "unknown"

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
            examples = config.get("examples", [])
            if examples:
                prompt += "\nExamples:\n" + json.dumps(examples, ensure_ascii=False, indent=2)
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

            if not self.llm_client or not self.llm_model:
                LOGGER.debug("multi-turn-mti skipped: llm_client_or_model_missing")
                return None

            system_content = prompt
            user_payload = {
                "previous_slots": previous_slots,
                "user_message": user_message,
            }

            # Add pronoun context if we have an active entity
            if state.active_topic and state.active_topic.get("value"):
                active_name = state.active_topic["value"]
                pronoun_hint = (
                    "When the user uses pronouns like 'her', 'him', or 'them', "
                    f"assume they refer to '{active_name}' unless the user explicitly "
                    "mentions a different entity."
                )
                system_content = system_content + "\n\n" + pronoun_hint

            try:
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                    ],
                )
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("multi-turn-mti llm_call_failed", error=str(exc))
                return None

            try:
                raw = response.choices[0].message.content  # type: ignore[index]
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("multi-turn-mti missing_response_content", error=str(exc))
                return None

            if not raw:
                LOGGER.warning("multi-turn-mti empty_response")
                return None

            try:
                decision = json.loads(raw)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("multi-turn-mti json_parse_failed", error=str(exc))
                return None

            required_keys = {"decision", "reason", "slots", "fused_query"}
            if not required_keys.issubset(decision.keys() if isinstance(decision, dict) else set()):
                LOGGER.warning("multi-turn-mti invalid_payload", payload_type=type(decision).__name__)
                return None

            return decision
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("multi-turn-mti failed", error=str(exc))
            return None

    def _apply_json_decision_rules(
        self,
        previous_slots: Dict[str, Optional[str]],
        user_message: str,
        state: Optional[ConversationState] = None,
    ) -> Optional[Dict[str, Any]]:
        """Lightweight, JSON-driven decision classifier prior to legacy heuristics."""

        config = self.multi_turn_config or {}
        decision_types = config.get("decision_types", {}) if isinstance(config, dict) else {}
        defaults = config.get("defaults", {}) if isinstance(config, dict) else {}

        text = (user_message or "").lower()
        if not text:
            return None

        def _default_decision(decision_key: str) -> str:
            mapping = {
                "time_only_followup": "fuse",
                "provider_time_followup": "fuse",
                "metric_followup": "fuse",
                "list_followup": "fuse",
                "new_topic": "new_topic",
                "clarification_needed": "clarification",
            }
            return mapping.get(decision_key, "clarification")

        def _base_slots(decision_key: str) -> Dict[str, Optional[str]]:
            slots = dict(previous_slots or {})
            decision_cfg = decision_types.get(decision_key, {}) if isinstance(decision_types, dict) else {}
            return slots

        def _apply_slot_policies(decision_key: str, slots: Dict[str, Optional[str]]) -> None:
            inherit_list = decision_types.get(decision_key, {}).get("inherits_slots", [])
            reset_list = decision_types.get(decision_key, {}).get("resets_slots", [])

            for key in reset_list:
                slots[key] = None

            for key in inherit_list:
                if key in previous_slots and slots.get(key) is None:
                    slots[key] = previous_slots[key]

            period_cfg = self.multi_turn_config.get("period_handling", {})

            if period_cfg.get("inherit_if_followup") and previous_slots.get("time_window_kind"):
                if slots.get("time_window_kind") in (None, "unspecified"):
                    slots["time_window_kind"] = previous_slots.get("time_window_kind")

            if decision_key == "new_topic" and period_cfg.get("clear_if_new_topic"):
                slots["time_window_kind"] = None

        # time_only_followup
        if decision_types.get("time_only_followup") and (
            self._is_time_only(user_message) or self._contains_time_phrase(text)
        ):
            slots = _base_slots("time_only_followup")
            slots.update(previous_slots or {})
            period_info = self._extract_period_info(user_message, state)
            time_window = period_info.get("last_period_type") or period_info.get("last_month")
            if period_info.get("last_month"):
                # Carry forward the explicit month label (e.g., "July") so the fused
                # query keeps natural language that NLV can parse.
                slots["month_label"] = period_info.get("last_month")
            if time_window == "explicit_month" or period_info.get("last_month"):
                slots["time_window_kind"] = "explicit_month"
            elif period_info.get("last_period_type"):
                slots["time_window_kind"] = period_info.get("last_period_type")
            else:
                slots["time_window_kind"] = (
                    slots.get("time_window_kind")
                    or defaults.get("default_time_window_kind_if_unspecified")
                    or "unspecified"
                )
            _apply_slot_policies("time_only_followup", slots)
            fused_query = self._compose_fused_query(slots, user_message)
            return {
                "decision": _default_decision("time_only_followup"),
                "reason": "Detected time-only follow-up via JSON patterns",
                "slots": slots,
                "fused_query": fused_query,
            }

        # provider_time_followup (pronoun + provider/time focus)
        if decision_types.get("provider_time_followup") and previous_slots.get("entity_role") == "student":
            pronoun_hit = self._contains_pronoun(text)
            time_hit = self._contains_time_phrase(text)
            provider_hit = self._contains_provider_focus(text)
            if pronoun_hit and (time_hit or provider_hit):
                slots = _base_slots("provider_time_followup")
                slots.update(
                    {
                        "entity_role": previous_slots.get("entity_role"),
                        "entity_name": previous_slots.get("entity_name"),
                        "mode": decision_types.get("provider_time_followup", {}).get(
                            "sets_mode", "student_provider_breakdown"
                        ),
                        "plan_kind": None,
                        "metric": "hours",
                    }
                )
                strict_key = ("student", "hours")
                slots["plan_kind"] = self.METRIC_PLAN_MAP.get(
                    strict_key, "student_provider_breakdown"
                )
                period_info = self._extract_period_info(user_message, state)
                if period_info.get("last_month"):
                    # Preserve the explicit month name from the follow-up question
                    # (e.g., "in July") so it appears in the fused query.
                    slots["month_label"] = period_info.get("last_month")
                if period_info.get("last_period_type"):
                    slots["time_window_kind"] = period_info.get("last_period_type")
                elif period_info.get("last_month"):
                    slots["time_window_kind"] = "explicit_month"
                _apply_slot_policies("provider_time_followup", slots)
                fused_query = self._compose_fused_query(slots, user_message)
                return {
                    "decision": _default_decision("provider_time_followup"),
                    "reason": "Pronoun + provider/time phrase follow-up detected",
                    "slots": slots,
                    "fused_query": fused_query,
                }

        # metric_followup
        metric_switch = self._get_pattern_list("metric_switch_phrases", {})
        if decision_types.get("metric_followup") and isinstance(metric_switch, dict):
            for metric, phrases in metric_switch.items():
                if any(p.lower() in text for p in phrases):
                    slots = _base_slots("metric_followup")
                    slots.update(previous_slots or {})
                    slots["metric"] = metric
                    slots["plan_kind"] = slots.get("plan_kind")
                    entity_role = previous_slots.get("entity_role")
                    strict_key = (entity_role, metric)
                    if strict_key in self.METRIC_PLAN_MAP:
                        slots["plan_kind"] = self.METRIC_PLAN_MAP[strict_key]
                    _apply_slot_policies("metric_followup", slots)
                    fused_query = self._compose_fused_query(slots, user_message)
                    return {
                        "decision": _default_decision("metric_followup"),
                        "reason": f"Metric switch phrase detected for {metric}",
                        "slots": slots,
                        "fused_query": fused_query,
                    }

        # list_followup
        list_refs = self._get_pattern_list("list_reference_phrases", [])
        if decision_types.get("list_followup") and any(ref in text for ref in list_refs):
            slots = _base_slots("list_followup")
            slots.update(previous_slots or {})
            _apply_slot_policies("list_followup", slots)
            fused_query = self._compose_fused_query(slots, user_message)
            return {
                "decision": _default_decision("list_followup"),
                "reason": "List follow-up phrase detected",
                "slots": slots,
                "fused_query": fused_query,
            }

        reset_triggers = self._get_topic_pattern_list("reset_triggers", [])
        if decision_types.get("new_topic") and any(trig in text for trig in reset_triggers):
            slots = _base_slots("new_topic")
            _apply_slot_policies("new_topic", slots)
            fused_query = user_message
            return {
                "decision": _default_decision("new_topic"),
                "reason": "Reset trigger detected",
                "slots": slots,
                "fused_query": fused_query,
            }

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

        if slots.get("mode") in {"top_invoices", "invoice_details"}:
            invoice_candidates = slots.get("invoice_numbers") or slots.get(
                "invoice_candidates"
            )
            if invoice_candidates is None and state.candidate_entities:
                invoice_candidates = state.candidate_entities
            if isinstance(invoice_candidates, (list, tuple)):
                state.last_invoice_candidates = [str(i) for i in invoice_candidates]

        plan_kind = slots.get("plan_kind")
        if plan_kind:
            state.last_plan_kind = plan_kind

        time_window_kind = slots.get("time_window_kind")
        if time_window_kind:
            state.last_period_type = time_window_kind

    def _detect_time_followup(
        self, user_message: Optional[str], state: ConversationState
    ) -> Optional[Dict[str, str]]:
        """
        Detect month-only follow-ups that should inherit the active topic.

        Returns an object with month and time window details when the message is only a
        month reference.
        """

        if not user_message or not state or not state.active_topic:
            return None

        normalized = re.sub(r"[?.!]", "", user_message).strip().lower()
        if not normalized:
            return None

        if self._extract_name(user_message):
            return None

        month_pattern = (
            r"^(?:just\s+|only\s+|for\s+|in\s+)?"
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\b$"
        )
        match = re.match(month_pattern, normalized)
        if not match:
            return None

        month_name = match.group(1).title()
        today = date.today()
        current_year = today.year
        if today.month >= 7:
            start_year = current_year
            end_year = current_year + 1
        else:
            start_year = current_year - 1
            end_year = current_year

        state.last_period_start = f"{start_year}-07-01"
        state.last_period_end = f"{end_year}-06-30"

        return {
            "month": month_name,
            "time_window_kind": "explicit_month",
            "last_period_start": state.last_period_start,
            "last_period_end": state.last_period_end,
        }

    def _compose_fused_query(
        self,
        slots: Dict[str, Any],
        user_message: str,
        previous_query: Optional[str] = None,
    ) -> str:
        """
        Always preserve the user_message semantics and append it to the previous query.
        """
        if previous_query:
            return f"{previous_query}. Additional instruction: {user_message}".strip()
        return user_message.strip()

    def _apply_mti_decision(
        self,
        decision: Dict[str, Any],
        state: ConversationState,
        session_id: str,
        user_message: str,
        required_slots: Optional[List[str]],
        new_intent_shape: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Apply an MTI decision to the state and return a response payload."""

        if not decision:
            return None

        decision_type = decision.get("decision")
        slots = decision.get("slots") or {}

        previous_slots = self._build_previous_slots(state)

        pronoun_slots = self._extract_entities_from_message(user_message, state)
        slots = self._merge_slots(
            pronoun_slots,
            slots,
        )

        reason = decision.get("reason")

        intent_mismatch = (
            state.last_intent_shape is not None
            and new_intent_shape is not None
            and new_intent_shape != state.last_intent_shape
        )

        # ------------------------------------------------------------------
        # VENDOR GUARD:
        # Never allow a fused query that says "the vendor" with no vendor_name.
        #
        # For example, inputs like:
        #   "how much are we paying agencies"
        # should either:
        #   (a) ask which agency, or
        #   (b) be routed as "all vendors" at the district level.
        #
        # If we see a vendor-mode plan without an entity_name, force a
        # clarification asking for the vendor_name instead of fusing.
        # ------------------------------------------------------------------
        vendor_mode = slots.get("mode") == "vendor_monthly"
        vendor_plan = slots.get("plan_kind") == "vendor_monthly_spend"
        vendor_role = slots.get("entity_role") == "vendor"
        if (vendor_mode or vendor_plan or vendor_role) and not slots.get("entity_name"):
            state.missing_slots = ["vendor_name"]
            decision_type = "clarification"
            reason = reason or (
                "Which agency or vendor do you want to look at? "
                "If you mean all agencies, please say 'all agencies'."
            )
            decision["reason"] = reason

        if pronoun_slots.get("missing_slot"):
            state.missing_slots = [pronoun_slots["missing_slot"]]
            decision_type = "clarification"
            decision["reason"] = reason or "Need invoice number from previous list."
            if pronoun_slots.get("clarification_prompt"):
                decision["reason"] = pronoun_slots["clarification_prompt"]

        if intent_mismatch and decision_type != "new_topic":
            decision_type = "new_topic"
            decision["reason"] = reason or "Analytic intent changed; starting new topic."
            reason = decision["reason"]

        time_followup = self._detect_time_followup(user_message, state)
        if time_followup:
            slots = self._merge_slots(previous_slots, slots)
            slots["time_window_kind"] = time_followup.get(
                "time_window_kind", "explicit_month"
            )
            month = time_followup.get("month")
            slots["month"] = month
            state.last_month = month
            state.last_explicit_month = month
            state.last_period_type = slots["time_window_kind"]
            state.last_period_start = time_followup.get("last_period_start")
            state.last_period_end = time_followup.get("last_period_end")
            decision_type = "time_only_followup"
            decision["reason"] = decision.get("reason") or "Month-only follow-up detected; inheriting active topic."
        else:
            slots = self._merge_slots(previous_slots, slots)
        previous_query = state.original_query
        if not previous_query and isinstance(state.active_topic, dict):
            previous_query = state.active_topic.get("last_query")
        fused_query = self._compose_fused_query(slots, user_message, previous_query)
        LOGGER.debug(
            "mti-decision",
            decision_type=decision_type,
            slots=slots,
            previous_query=previous_query,
            fused_query=fused_query,
            user_message=user_message,
        )
        if pronoun_slots and decision_type is None:
            decision_type = "fuse"
        reason = decision.get("reason")
        if pronoun_slots and decision_type == "clarification":
            if pronoun_slots.get("entity_role") or pronoun_slots.get("entity_name"):
                decision_type = "fuse"
                reason = (
                    reason
                    or "Resolved pronoun or placeholder to previous topic; fusing."
                )

        if decision_type == "clarification":
            state.latest_user_message = user_message
            state.history.append({"role": "user", "content": user_message})
            clarification_prompt = reason or self._build_clarification_prompt(state)
            self.save_state(state, session_id=session_id)
            LOGGER.debug("multi-turn-mti clarification", reason=reason)
            return {
                "needs_clarification": True,
                "fused_query": None,
                "state": state.to_dict(),
            }

        if decision_type == "new_topic":
            self.clear_state(session_id)
            previous_query = None
            prior_original_query = state.original_query
            state = self._start_new_thread(user_message, required_slots)
            fused_query = self._compose_fused_query(slots, user_message, previous_query)
            self._apply_mti_slots(state, slots, fused_query)
            state.last_intent_shape = new_intent_shape
            if prior_original_query is None:
                state.original_query = user_message
            else:
                state.original_query = prior_original_query
            state.latest_user_message = user_message
            state.history.append({"role": "user", "content": user_message})
            needs_clarification = bool(state.missing_slots)
            self.save_state(state, session_id=session_id)
            print("[multi-turn-debug] USING _compose_fused_query:", fused_query)
            LOGGER.debug("multi-turn-mti new_topic", fused_query=fused_query)
            return {
                "needs_clarification": needs_clarification,
                "fused_query": fused_query,
                "state": state.to_dict(),
            }

        is_time_only_followup = decision_type == "time_only_followup"

        if decision_type in {"fuse", "time_only_followup"}:
            state.latest_user_message = user_message
            state.history.append({"role": "user", "content": user_message})
            fused_query = self._compose_fused_query(slots, user_message, previous_query)
            self._apply_mti_slots(state, slots, fused_query)
            state.last_intent_shape = new_intent_shape
            if state.active_topic:
                state.active_topic["last_query"] = fused_query

            # --------------------------------------------------------------
            # SAFETY RULE: CLEAR ENTITY CONTEXT FOR INVOICE/DISTRICT MODES
            #
            # These modes are NOT student-scoped. Inheriting an active_topic
            # (e.g., student name) causes invalid SQL and logic failures.
            #
            # Modes:
            #   - top_invoices
            #   - invoice_details
            #   - district_monthly
            #   - district_daily
            #
            # When triggered, wipe active_topic so downstream SQL and routing
            # do NOT apply student/vendor/provider filters incorrectly.
            # --------------------------------------------------------------
            invoice_or_district_modes = {
                "top_invoices",
                "invoice_details",
                "district_monthly",
                "district_daily",
            }
            if state.active_mode in invoice_or_district_modes:
                state.active_topic = {}
            if not state.original_query:
                state.original_query = user_message
            needs_clarification = False if is_time_only_followup else bool(state.missing_slots)
            self.save_state(state, session_id=session_id)
            print("[multi-turn-debug] USING _compose_fused_query:", fused_query)
            LOGGER.debug("multi-turn-mti fused", fused_query=fused_query)
            return {
                "needs_clarification": needs_clarification,
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
        def _state_value(state_obj: Any, key: str) -> Any:
            if hasattr(state_obj, key):
                try:
                    return getattr(state_obj, key)
                except Exception:
                    return None
            if isinstance(state_obj, dict):
                return state_obj.get(key)
            return None

        def _state_to_dict(state_obj: Any) -> Dict[str, Any]:
            if hasattr(state_obj, "to_dict"):
                try:
                    return state_obj.to_dict()  # type: ignore[call-arg]
                except Exception:
                    pass
            try:
                return dict(state_obj or {})
            except Exception:
                return {}

        def _log_and_return(
            needs_clarification: bool, fused_query: Optional[str], state_obj: Any
        ) -> Dict[str, Any]:
            state_dict = _state_to_dict(state_obj)
            print("[multi-turn-debug] FUSION TRACE:")
            print(f"  - session_id: {session_id}")
            print(f"  - active_topic: {_state_value(state_obj, 'active_topic')}")
            print(f"  - original_query: {_state_value(state_obj, 'original_query')}")
            print(f"  - latest_user_message: {user_message}")
            print(f"  - last_plan_kind: {_state_value(state_obj, 'last_plan_kind')}")
            print(f"  - last_period_start: {_state_value(state_obj, 'last_period_start')}")
            print(f"  - last_period_end: {_state_value(state_obj, 'last_period_end')}")
            print(f"  - last_month: {_state_value(state_obj, 'last_month')}")
            print(f"  - fusion: {'YES' if fused_query else 'NO'}")
            print(f"  - fused_query: {fused_query or '<none>'}")

            LOGGER.debug(
                "multi-turn-return",
                session_id=session_id,
                needs_clarification=needs_clarification,
                fused_query=fused_query,
                state=state_dict,
            )

            return {
                "needs_clarification": needs_clarification,
                "fused_query": fused_query,
                "state": state_dict,
            }

        if user_message.strip().lower() == "reset please":
            self.clear_state(session_id)
            print("[multi-turn] state cleared by user command", flush=True)
            state = ConversationState()
            fused_query = locals().get("fused_query")
            return _log_and_return(
                False,
                "reset",
                {},
            )

        user_message = user_message.strip()
        state = self.get_state(session_id)
        new_intent_shape = self._infer_intent_shape(user_message)

        active_mode = getattr(state, "active_mode", None)
        last_query = None
        if isinstance(state.active_topic, dict):
            last_query = state.active_topic.get("last_query")
        if last_query is None:
            last_query = state.original_query
        intent_mismatch = (
            state.last_intent_shape is not None
            and new_intent_shape is not None
            and new_intent_shape != state.last_intent_shape
        )

        mti_decision: Optional[Dict[str, Any]] = None
        if self.multi_turn_config:
            try:
                mti_decision = self._run_mti(state, user_message)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.warning("multi-turn-mti invocation_failed", error=str(exc))

        if mti_decision:
            applied = self._apply_mti_decision(
                mti_decision,
                state,
                session_id,
                user_message,
                required_slots,
                new_intent_shape,
            )
            if applied:
                fused_query = applied.get("fused_query")
                needs_clarification = bool(applied.get("needs_clarification"))
                if fused_query:
                    print(
                        "[multi-turn-debug] USING _compose_fused_query:",
                        fused_query,
                    )
                return _log_and_return(needs_clarification, fused_query, state)

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
            and not intent_mismatch
        )

        if message_is_time_only and not time_only_followup:
            return _reset_thread_and_return()

        json_decision = None
        if not intent_mismatch:
            json_decision = self._apply_json_decision_rules(
                self._build_previous_slots(state), user_message, state
            )
        if json_decision:
            slots = json_decision.get("slots", {}) or {}
            fused_query = self._compose_fused_query(slots, user_message, last_query)
            self._apply_mti_slots(state, slots, fused_query)
            state.last_intent_shape = new_intent_shape
            needs_clarification = json_decision.get("decision") == "clarification"
            self.save_state(state, session_id=session_id)
            print("[multi-turn-debug] USING _compose_fused_query:", fused_query)
            return _log_and_return(needs_clarification, fused_query, state)

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
            return _log_and_return(needs_clarification, fused_query, fresh_state)

        if self._should_reset_topic(user_message, state):
            return _reset_thread_and_return()

        fallback_decision = self._fallback_decision(user_message)
        if fallback_decision == "new_topic":
            return _reset_thread_and_return()

        has_active_topic = state.original_query is not None

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
            return _log_and_return(needs_clarification, fused_query, state)

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
            return _log_and_return(needs_clarification, fused_query, state)

        is_short_wh_followup = (
            self._is_short_wh_followup(user_message) if has_active_topic else False
        )

        starts_new_topic = self._starts_new_topic(user_message, state)
        if intent_mismatch:
            starts_new_topic = True

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
            return _log_and_return(needs_clarification, fused_query, state)

        # Follow-up message keeps the existing thread
        state.history.append({"role": "user", "content": user_message})
        state.latest_user_message = user_message

        period_info = self._extract_period_info(user_message, state)
        is_followup = self._is_followup_message(user_message)
        lower_message = user_message.lower()

        if period_info.get("has_explicit_period"):
            for field_name in [
                "last_period_type",
                "last_period_start",
                "last_period_end",
                "last_month",
                "last_explicit_month",
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
                "last_explicit_month",
                "last_year_window",
            ]:
                if period_info.get(field_name) is None:
                    period_info[field_name] = getattr(state, field_name)

        for field_name in [
            "last_period_type",
            "last_period_start",
            "last_period_end",
            "last_month",
            "last_explicit_month",
            "last_year_window",
        ]:
            if field_name in period_info and period_info[field_name] is not None:
                setattr(state, field_name, period_info[field_name])

        if required_slots is not None and not state.missing_slots:
            state.missing_slots = list(required_slots)

        self._attempt_slot_fill(state, user_message, allow_fallback_value=True)

        needs_clarification = bool(state.missing_slots)
        fused_query = self._compose_fused_query({}, user_message, last_query)
        state.last_intent_shape = new_intent_shape
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
        print("[multi-turn-debug] USING _compose_fused_query:", fused_query)
        return _log_and_return(needs_clarification, fused_query, state)

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
            last_explicit_month=period_info.get("last_explicit_month"),
            last_year_window=period_info.get("last_year_window"),
            last_intent_shape=self._infer_intent_shape(user_message),
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
            if any(prefix in text for prefix in pronoun_starts) or self._contains_pronoun(text):
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

        connectors = [
            "what about ",
            "how about ",
            "and ",
            "now ",
            "then ",
            "just ",
            "for ",
            "in ",
            "show ",
            "show me ",
        ]
        for prefix in connectors:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].strip()

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

        if re.match(month_pattern, normalized):
            return True

        trailing_tokens = {"only", "please", "instead", "now"}
        normalized_tokens = [tok for tok in normalized.split() if tok]
        if len(normalized_tokens) >= 2 and any(
            re.match(month_pattern, token) for token in normalized_tokens
        ):
            remaining = [tok for tok in normalized_tokens if not re.match(month_pattern, tok)]
            if all(tok in trailing_tokens for tok in remaining):
                return True

        return False

    def _extract_period_info(
        self, message: str, state: Optional[ConversationState] = None
    ) -> Dict[str, Optional[str]]:
        info: Dict[str, Optional[str]] = {
            "last_period_type": None,
            "last_period_start": None,
            "last_period_end": None,
            "last_month": None,
            "last_explicit_month": None,
            "last_year_window": None,
            "has_explicit_period": False,
        }

        if not message:
            return info

        text = message.lower()

        if "that month" in text and state and state.last_month:
            info["last_month"] = state.last_month
            info["last_period_type"] = "explicit_month"
            info["last_explicit_month"] = state.last_month
            return info

        # Detect explicit month phrases like "in July" or "for September"
        months = [
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
        lower_msg = text
        for m in months:
            if f"in {m}" in lower_msg or f"for {m}" in lower_msg:
                info["last_explicit_month"] = m.capitalize()
                info["last_month"] = m.capitalize()
                info["last_period_type"] = "explicit_month"
                return info

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
        allowed_singletons = set(
            self.multi_turn_config.get("single_token_student_names", [])
            if self.multi_turn_config
            else []
        )
        wh_words = {"which", "what", "who", "how"}

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
            if len(tokens) == 1:
                token = tokens[0]
                if token.lower() in wh_words or token not in allowed_singletons:
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
            if len(tokens) == 1:
                token = tokens[0]
                if token.lower() in wh_words or token not in allowed_singletons:
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

        reset_triggers = self._get_topic_pattern_list("reset_triggers", [])
        if any(trig in text for trig in reset_triggers):
            return True

        if state.active_topic:
            if self._contains_time_phrase(text):
                return False
            if self._contains_pronoun(text):
                return False

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
        """
        Build a user-facing clarification prompt based on missing slots.

        Default behaviour is a simple "I need the following additional details: …"
        but we special-case common analytics follow-ups to make them more natural.
        """

        if not state.missing_slots:
            return None

        # Special case: asking for invoice details without an invoice_number.
        # This covers flows like:
        #   - "show top invoices"
        #   - "can I see the line-item details for that?"
        # where we need the user to pick a specific invoice number.
        if len(state.missing_slots) == 1 and state.missing_slots[0] == "invoice_number":
            active_mode = getattr(state, "active_mode", None)
            last_plan = getattr(state, "last_plan_kind", None)
            if active_mode in {"top_invoices", "invoice_details"} or last_plan in {"top_invoices"}:
                return (
                    "I need the invoice number so I know which invoice to show line-item details for. "
                    "Please provide the invoice number you have in mind."
                )

        # Default generic clarification
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

        month_followup = None
        if state.latest_user_message and state.active_topic:
            month_followup = self._detect_time_followup(state.latest_user_message, state)

        if state.latest_user_message and state.latest_user_message != state.original_query:
            if (
                state.latest_user_message not in state.resolved_slots.values()
                and not month_followup
            ):
                parts.append(f"Additional instruction: {state.latest_user_message}")

        return " ".join(part.strip() for part in parts if part).strip()

    def _contains_pronoun(self, text: str) -> bool:
        pronouns = {"he", "him", "his", "she", "her", "hers", "they", "them"}
        patterns = self._get_pattern_list("pronoun_followup_starters", [])
        lowered = text.lower()
        return any(p in lowered for p in pronouns) or any(p in lowered for p in patterns)

    def _extract_entities_from_message(
        self, user_message: Optional[str], state: ConversationState
    ) -> Dict[str, Optional[str]]:
        """
        Resolve pronoun/placeholder references to the active topic when possible.
        """

        results: Dict[str, Optional[str]] = {}
        if not user_message or not state:
            return results

        lowered = user_message.lower()
        active_role = state.active_topic.get("type") if state.active_topic else None
        active_value = state.active_topic.get("value") if state.active_topic else None

        placeholder_terms = {
            "the ones",
            "those ones",
            "the people",
            "the kids",
            "the providers",
        }
        pronoun_hit = bool(
            re.search(r"\b(he|she|they|him|her|them)\b", lowered)
            or any(term in lowered for term in placeholder_terms)
            or any(term in lowered for term in ["that month", "that student"])
        )

        if pronoun_hit and active_role:
            results["entity_role"] = active_role
            if active_value:
                results["entity_name"] = active_value

        invoice_reference_terms = {
            "that invoice",
            "that one",
            "that",
            "the biggest one",
        }
        if not state.active_topic and any(term in lowered for term in invoice_reference_terms):
            candidates = getattr(state, "last_invoice_candidates", []) or []
            if len(candidates) == 1:
                results["entity_role"] = "invoice"
                results["entity_name"] = str(candidates[0])
            elif len(candidates) > 1:
                results["missing_slot"] = "invoice_number"
                choice_text = ", ".join(str(c) for c in candidates)
                results["clarification_prompt"] = (
                    f"Which invoice number do you want? You can choose from: {choice_text}"
                )

        placeholder_entity_terms = {"the ones", "the kids", "the providers", "the people"}
        if any(term in lowered for term in placeholder_entity_terms):
            inferred_role = None
            if state.active_mode == "student_list":
                inferred_role = "student"
            elif state.active_mode in {"clinician_student_breakdown", "provider_monthly"}:
                inferred_role = "clinician"
            elif state.active_mode == "vendor_monthly":
                inferred_role = "vendor"
            if inferred_role:
                results.setdefault("entity_role", inferred_role)

        return results

    def _contains_provider_focus(self, text: str) -> bool:
        providers = self._get_pattern_list("provider_focus_phrases", [])
        lowered = text.lower()
        return any(p in lowered for p in providers)

    def _contains_time_phrase(self, text: str) -> bool:
        time_phrases = self._get_pattern_list("time_shift_phrases", [])
        lowered = text.lower()
        if any(p in lowered for p in time_phrases):
            return True
        return bool(
            re.search(
                r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
                lowered,
            )
        )


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
