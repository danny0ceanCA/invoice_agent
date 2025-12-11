"""Optional post-processing hook for analytics agent output."""

from __future__ import annotations

from typing import Any, Mapping


def run_render_model(final_output: Any) -> Any:
    """Return enhanced output when available.

    The render model is intentionally optional and should not interfere with the
    primary analytics pipeline. It accepts the final output payload produced by
    the logic model and may return an updated mapping with keys ``text``,
    ``html``, and ``rows``. If no enhancement is performed, the original value
    is returned unchanged.
    """

    if isinstance(final_output, Mapping):
        return {
            "text": final_output.get("text"),
            "html": final_output.get("html"),
            "rows": final_output.get("rows"),
        }
    return final_output


__all__ = ["run_render_model"]
