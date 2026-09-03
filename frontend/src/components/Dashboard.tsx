import { useEffect, useState } from "react";
import { useStore } from "../store/useStore";
import { apiClient } from "../services/api";
import { useVideoPolling } from "../hooks/useVideoPolling";
import VideoUpload from "./VideoUpload";
import VideoList from "./VideoList";
import ClipGrid from "./ClipGrid";
import { Video } from "../types";

export default function Dashboard() {
  const { videos, setVideos, selectedVideo, setSelectedVideo, user, logout } =
    useStore();
  const [loading, setLoading] = useState(true);

  useVideoPolling();

  useEffect(() => {
    (async () => {
      try {
        const result = await apiClient.listVideos(0, 50);
        setVideos(result.videos);
      } catch {
        /* the list stays empty; the empty state explains what to do */
      } finally {
        setLoading(false);
      }
    })();
  }, [setVideos]);

  const openVideo = (video: Video) => setSelectedVideo(video);

  // Keep the open video in sync with polled updates so its progress moves
  const liveSelected = selectedVideo
    ? videos.find((v) => v.id === selectedVideo.id) || selectedVideo
    : null;

  return (
    <div className="relative min-h-screen">
      <header
        className="sticky top-0 z-20 border-b backdrop-blur"
        style={{
          borderColor: "var(--border)",
          background: "rgba(11,13,18,0.8)",
        }}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3.5">
          <button
            onClick={() => setSelectedVideo(null)}
            className="flex items-center gap-2.5"
          >
            <span
              className="flex h-8 w-8 items-center justify-center rounded-lg text-base"
              style={{ background: "var(--accent-soft)" }}
            >
              ✂️
            </span>
            <span className="font-semibold tracking-tight">Clip Generator</span>
          </button>

          <div className="flex items-center gap-3">
            <span className="hidden text-sm sm:block" style={{ color: "var(--text-dim)" }}>
              {user?.username}
            </span>
            <button onClick={logout} className="btn btn-ghost !px-3 !py-1.5">
              Salir
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        {liveSelected ? (
          <ClipGrid video={liveSelected} onBack={() => setSelectedVideo(null)} />
        ) : (
          <>
            <VideoUpload />
            <VideoList
              loading={loading}
              onOpen={openVideo}
            />
          </>
        )}
      </main>
    </div>
  );
}
