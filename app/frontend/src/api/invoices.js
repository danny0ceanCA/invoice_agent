import { API_BASE } from "./auth";

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

  const response = await fetch(`${API_BASE}/invoices/generate`, {
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

export async function fetchInvoicePresignedUrl(s3Key, accessToken) {
  if (!s3Key) {
    throw new Error("Missing S3 key for invoice download");
  }

  if (!accessToken) {
    throw new Error("Missing access token");
  }

  const response = await fetch(
    `${API_BASE}/invoices/presign?s3_key=${encodeURIComponent(s3Key)}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  );

  if (!response.ok) {
    const message = await response.text();
    throw new Error(
      message || `Failed to fetch presigned URL (status ${response.status})`,
    );
  }

  return response.json();
}
