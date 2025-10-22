import axios from "axios";

interface UploadMetadata {
  vendor_id: number;
  invoice_date: string;
  service_month: string;
}

export async function uploadInvoice(file: File, meta: UploadMetadata): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("vendor_id", String(meta.vendor_id));
  formData.append("invoice_date", meta.invoice_date);
  formData.append("service_month", meta.service_month);

  await axios.post("/api/invoices/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}
