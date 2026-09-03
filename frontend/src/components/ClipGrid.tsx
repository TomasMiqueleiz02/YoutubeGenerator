import { useEffect, useState } from "react";
import { apiClient } from "../services/api";
import { Clip, Video } from "../types";

interface Props {
  video: Video;
  onBack: () => void;
}

function timecode(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ClipGrid({ video, onBack }: Props) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);

  const done = video.status === "completed";

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const result = await apiClient.getClipsForVideo(video.id);
        if (!cancelled) setClips(result.clips);
      } catch {
        /* leave clips empty; the empty state covers it */
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    // While the video is still being processed, clips appear gradually
    const timer = !done ? window.setInterval(load, 5000) : null;
    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
    };
  }, [video.id, done]);

  const sorted = [...clips].sort(
    (a, b) => (b.virality_score || 0) - (a.virality_score || 0)
  );

  return (
    <>
      <button
        onClick={onBack}
        className="mb-5 text-sm"
        style={{ color: "var(--text-dim)" }}
      >
        ← Volver a mis videos
      </button>

      <div className="mb-7">
        <h1 className="text-2xl font-bold leading-tight tracking-tight">
          {video.title || "Sin título"}
        </h1>
        <p className="mt-1.5 text-sm" style={{ color: "var(--text-dim)" }}>
          {done
            ? `${clips.length} ${clips.length === 1 ? "clip generado" : "clips generados"}`
            : "Procesando. Los clips aparecen a medida que se generan."}
        </p>
      </div>

      {!done && (
        <div className="card mb-6 p-4">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span>Progreso</span>
            <span style={{ color: "var(--text-dim)" }}>
              {Math.round(video.processing_progress)}%
            </span>
          </div>
          <div
            className="relative h-1.5 overflow-hidden rounded-full shimmer"
            style={{ background: "var(--border)" }}
          >
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{
                width: `${Math.max(4, video.processing_progress)}%`,
                background: "var(--accent)",
              }}
            />
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card aspect-[9/16] animate-pulse" />
          ))}
        </div>
      ) : sorted.length === 0 ? (
        <div className="card flex flex-col items-center py-16 text-center">
          <div className="mb-3 text-3xl opacity-60">{done ? "🤔" : "⏳"}</div>
          <p className="font-medium">
            {done ? "No se encontraron momentos" : "Todavía no hay clips"}
          </p>
          <p className="mt-1.5 max-w-sm text-sm" style={{ color: "var(--text-dim)" }}>
            {done
              ? "El video no tenía segmentos que funcionaran como clip independiente."
              : "Aparecen acá apenas se generen."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((clip, index) => (
            <ClipCard key={clip.id} clip={clip} rank={index + 1} />
          ))}
        </div>
      )}
    </>
  );
}

function ClipCard({ clip, rank }: { clip: Clip; rank: number }) {
  const [media, setMedia] = useState<{
    video_url: string | null;
    thumbnail_url: string | null;
  } | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!clip.file_path) return;
    apiClient
      .getClipMedia(clip.id)
      .then(setMedia)
      .catch(() => setFailed(true));
  }, [clip.id, clip.file_path]);

  const score = Math.round(clip.virality_score || 0);

  return (
    <article className="card overflow-hidden">
      <div className="relative aspect-[9/16]" style={{ background: "#000" }}>
        {media?.video_url ? (
          <video
            src={media.video_url}
            poster={media.thumbnail_url || undefined}
            controls
            preload="metadata"
            playsInline
            className="h-full w-full object-contain"
          />
        ) : (
          <div
            className="flex h-full flex-col items-center justify-center gap-2 text-sm"
            style={{ color: "var(--text-faint)" }}
          >
            {failed || !clip.file_path ? (
              <>
                <span className="text-2xl opacity-50">⚠️</span>
                <span>Video no disponible</span>
              </>
            ) : (
              <>
                <span className="text-2xl opacity-50">⏳</span>
                <span>Cargando...</span>
              </>
            )}
          </div>
        )}

        <span
          className="absolute left-2.5 top-2.5 rounded-md px-2 py-1 text-xs font-bold"
          style={{ background: "rgba(0,0,0,0.75)", color: "var(--accent)" }}
        >
          #{rank}
        </span>
      </div>

      <div className="p-4">
        {clip.title && (
          <h3 className="mb-1.5 line-clamp-2 text-sm font-semibold leading-snug">
            {clip.title}
          </h3>
        )}
        {clip.caption && (
          <p
            className="mb-3 line-clamp-2 text-xs italic leading-relaxed"
            style={{ color: "var(--text-dim)" }}
          >
            “{clip.caption}”
          </p>
        )}

        <div className="mb-3 flex items-center gap-3 text-xs" style={{ color: "var(--text-faint)" }}>
          <span>{timecode(clip.start_time)}</span>
          <span>·</span>
          <span>{Math.round(clip.duration)}s</span>
          <span className="ml-auto font-semibold" style={{ color: "var(--accent)" }}>
            {score}
          </span>
        </div>

        {media?.video_url && (
          <a
            href={media.video_url}
            download={`clip-${clip.id.slice(0, 8)}.mp4`}
            className="btn btn-ghost w-full !py-2 text-xs"
          >
            Descargar
          </a>
        )}
      </div>
    </article>
  );
}
