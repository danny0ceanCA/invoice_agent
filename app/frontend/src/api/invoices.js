const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function uploadInvoice(file, meta, accessToken) {
  if (!accessToken) {
    throw new Error("Missing access token");
  }
  const formData = new FormData();
  formData.append("file", file);
  formData.append("vendor_id", String(meta.vendor_id));
  formData.append("invoice_date", meta.invoice_date);
  formData.append("service_month", meta.service_month);
  if (meta.invoice_code) {
    formData.append("invoice_code", meta.invoice_code);
  }

  const response = await fetch(`${API_BASE}/api/invoices/generate`, {
    method: "POST",
    body: formData,
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to start invoice generation");
  }

  return response.json();
}
