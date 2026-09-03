import { useEffect, useRef } from "react";
import { apiClient } from "../services/api";
import { useStore } from "../store/useStore";

/**
 * Keeps the video list fresh while anything is still processing.
 *
 * Processing happens on a worker, so the page has no way to know a job
 * advanced. Without this the progress bar sits frozen and the app looks stuck
 * even when it is working.
 */
export function useVideoPolling(intervalMs = 4000) {
  const { videos, setVideos } = useStore();
  const timer = useRef<number | null>(null);

  const anyActive = videos.some((v) =>
    ["pending", "downloading", "downloaded", "processing", "analyzed"].includes(
      v.status
    )
  );

  useEffect(() => {
    if (!anyActive) {
      if (timer.current) {
        window.clearInterval(timer.current);
        timer.current = null;
      }
      return;
    }

    const tick = async () => {
      try {
        const result = await apiClient.listVideos(0, 50);
        setVideos(result.videos);
      } catch {
        // A failed refresh is not worth surfacing; the next tick retries.
      }
    };

    timer.current = window.setInterval(tick, intervalMs);
    return () => {
      if (timer.current) window.clearInterval(timer.current);
      timer.current = null;
    };
  }, [anyActive, intervalMs, setVideos]);
}
