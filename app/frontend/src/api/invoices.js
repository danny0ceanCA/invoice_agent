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

export async function fetchVendorInvoiceArchive(vendorId, month, accessToken) {
  if (vendorId == null) {
    throw new Error("Missing vendor identifier");
  }

  if (!month) {
    throw new Error("Missing month identifier");
  }

  if (!accessToken) {
    throw new Error("Missing access token");
  }

  const encodedMonth = encodeURIComponent(month);
  const response = await fetch(
    `${API_BASE}/invoices/download-zip/${vendorId}/${encodedMonth}`,
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
      message ||
        `Failed to fetch vendor invoice archive (status ${response.status})`,
    );
  }

  return response.json();
}

export async function requestInvoicesZip(vendorId, monthKey, accessToken) {
  if (vendorId == null || Number.isNaN(Number(vendorId))) {
    throw new Error("Missing vendor identifier");
  }

  if (!monthKey) {
    throw new Error("Missing invoice month key");
  }

  if (!accessToken) {
    throw new Error("Missing access token for ZIP request");
  }

  const response = await fetch(`/api/invoices/download-zip/${vendorId}/${monthKey}`, {
    method: "GET",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to prepare invoice archive: ${response.status}`);
  }

  const data = await response.json();

  const url =
    (typeof data?.url === "string" && data.url.trim()) ||
    (typeof data?.download_url === "string" && data.download_url.trim()) ||
    (typeof data?.downloadUrl === "string" && data.downloadUrl.trim()) ||
    "";

  if (!url) {
    throw new Error("Missing download URL in archive response");
  }

  return url;
}

export async function fetchVendorInvoicesForMonth(
  vendorId,
  year,
  month,
  accessToken,
) {
  if (vendorId == null || Number.isNaN(Number(vendorId))) {
    throw new Error("Missing vendor identifier");
  }

  if (year == null || Number.isNaN(Number(year))) {
    throw new Error("Missing invoice year");
  }

  if (month == null || Number.isNaN(Number(month))) {
    throw new Error("Missing invoice month");
  }

  if (!accessToken) {
    throw new Error("Missing access token");
  }

  const normalizedMonth = String(month).padStart(2, "0");
  const response = await fetch(
    `${API_BASE}/invoices/${encodeURIComponent(
      vendorId,
    )}/${encodeURIComponent(year)}/${encodeURIComponent(normalizedMonth)}`,
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
      message ||
        `Failed to fetch invoices for ${vendorId} (${year}-${normalizedMonth})`,
    );
  }

  return response.json();
}
