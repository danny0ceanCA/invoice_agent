"""Dataset profile utilities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DatasetProfile:
    """Represents the configuration used to process a vendor dataset."""

    name: str
    rules_json: dict


DEFAULT_PROFILE = DatasetProfile(
    name="SCUSD Baseline",
    rules_json={
        "required_columns": ["Client", "Schedule Date", "Hours", "Employee", "Service Code"],
        "filters": ["drop_zero_hours", "valid_service_month", "valid_service_code"],
        "calculations": ["apply_rate", "calc_cost"],
        "rates": {"HHA-SCUSD": 55, "LVN-SCUSD": 70, "RN-SCUSD": 85},
        "grouping_keys": ["Client", "Schedule Date", "Employee", "Service Code"],
    },
)
