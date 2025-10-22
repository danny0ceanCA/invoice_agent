import { useEffect, useState } from "react";
import { getJobStatus } from "../api/jobs";

export default function useJobPolling(id, interval = 4000, initialStatus = "queued", initialDownloadUrl = null) {
  const [status, setStatus] = useState(initialStatus);
  const [downloadUrl, setDownloadUrl] = useState(initialDownloadUrl);

  useEffect(() => {
    if (!id) return () => undefined;

    const tick = async () => {
      try {
        const result = await getJobStatus(id);
        setStatus(result.status);
        setDownloadUrl(result.download_url ?? null);
        if (["done", "error"].includes(result.status)) {
          clearInterval(timer);
        }
      } catch (error) {
        setStatus("error");
        clearInterval(timer);
      }
    };

    const timer = setInterval(tick, interval);
    tick();

    return () => clearInterval(timer);
  }, [id, interval]);

  return { status, downloadUrl };
}
