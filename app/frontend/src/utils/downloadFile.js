const INVALID_FILENAME_CHARS = /[\\/:*?"<>|]/g;

const decodeHeaderValue = (value) => {
  try {
    return decodeURIComponent(value);
  } catch (error) {
    return value;
  }
};

export const buildSafeFilename = (name, extension, fallbackBase = "download") => {
  const trimmed = typeof name === "string" ? name.trim() : "";
  const normalizedWhitespace = trimmed.replace(/\s+/g, " ").trim();
  const sanitizedBase = normalizedWhitespace.replace(INVALID_FILENAME_CHARS, "-");
  const base = sanitizedBase.length ? sanitizedBase : fallbackBase;

  if (!extension) {
    return base;
  }

  const normalizedExtension = extension.startsWith(".")
    ? extension
    : `.${extension}`;

  return base.toLowerCase().endsWith(normalizedExtension.toLowerCase())
    ? base
    : `${base}${normalizedExtension}`;
};

export const extractFilenameFromContentDisposition = (headerValue) => {
  if (!headerValue) {
    return null;
  }

  const filenameStarMatch = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (filenameStarMatch && filenameStarMatch[1]) {
    const filenameStar = filenameStarMatch[1].trim().replace(/^"|"$/g, "");
    return decodeHeaderValue(filenameStar);
  }

  const filenameMatch = headerValue.match(/filename="?([^";]+)"?/i);
  if (filenameMatch && filenameMatch[1]) {
    return decodeHeaderValue(filenameMatch[1].trim());
  }

  return null;
};

export const downloadFileFromPresignedUrl = async (
  presignedUrl,
  fallbackFilename = "",
) => {
  if (!presignedUrl) {
    throw new Error("A presigned download URL is required.");
  }

  const response = await fetch(presignedUrl);
  if (!response.ok) {
    throw new Error(`Failed to download file (status ${response.status})`);
  }

  const blob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition");
  const inferredFilename = extractFilenameFromContentDisposition(contentDisposition);
  const downloadName = inferredFilename ?? fallbackFilename ?? "";
  const blobUrl = window.URL.createObjectURL(blob);

  try {
    const link = document.createElement("a");
    link.href = blobUrl;

    if (downloadName) {
      link.download = downloadName;
    }

    link.rel = "noopener noreferrer";
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    window.URL.revokeObjectURL(blobUrl);
  }
};
