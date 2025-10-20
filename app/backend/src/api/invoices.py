"""Invoice related endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("")
async def list_invoices() -> list[dict[str, str]]:
    """Return an empty list of invoices until the service is implemented."""
    return []


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str) -> dict[str, str]:
    """Return a placeholder invoice payload."""
    return {"invoice_id": invoice_id, "status": "pending"}
