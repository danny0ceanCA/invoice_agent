from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path for imports
sys.path.append(str(Path(__file__).resolve().parents[4]))

from app.backend.src.agents.logic_model import _build_router_guidance


def test_router_guidance_respects_router_decision_contract():
    router_decision = {
        "mode": "invoice_details",
        "needs_invoice_details": True,
        "primary_entity_type": "invoice",
        "primary_entities": ["Example-INV-001"],
        "time_window": "month",
        "month_names": ["october"],
    }

    guidance = _build_router_guidance(router_decision)

    assert "ROUTER_DECISION (do not reinterpret):" in guidance
    assert "SQL_TEMPLATE_HINT: invoice_line_items_detail" in guidance
    assert "Follow the hinted template and RouterDecision exactly" in guidance
    assert '"needs_invoice_details": true' in guidance
    assert '"primary_entities": ["Example-INV-001"]' in guidance
