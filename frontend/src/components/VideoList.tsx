import { useStore } from "../store/useStore";
import { apiClient } from "../services/api";
import { Video } from "../types";

interface Props {
  loading: boolean;
  onOpen: (video: Video) => void;
}

/** Plain-language stage labels: "processing 60%" means nothing on its own. */
const STAGES: Record<string, { label: string; tone: string }> = {
  pending: { label: "En cola", tone: "var(--text-dim)" },
  downloading: { label: "Descargando", tone: "var(--warn)" },
  downloaded: { label: "Descargado", tone: "var(--warn)" },
  processing: { label: "Analizando", tone: "var(--warn)" },
  analyzed: { label: "Cortando clips", tone: "var(--warn)" },
  completed: { label: "Listo", tone: "var(--good)" },
  error: { label: "Falló", tone: "var(--bad)" },
};

function formatDuration(seconds?: number) {
  if (!seconds) return null;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function VideoList({ loading, onOpen }: Props) {
  const { videos, setVideos } = useStore();

  const remove = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setVideos(videos.filter((v) => v.id !== id));
    try {
      await apiClient.deleteVideo(id);
    } catch {
      /* the row is already gone locally; a refresh restores truth */
    }
  };

  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="card h-44 animate-pulse" />
        ))}
      </div>
    );
  }

  if (videos.length === 0) {
    return (
      <div className="card flex flex-col items-center py-16 text-center">
        <div className="mb-3 text-3xl opacity-60">🎬</div>
        <p className="font-medium">Todavía no hay videos</p>
        <p className="mt-1.5 max-w-xs text-sm" style={{ color: "var(--text-dim)" }}>
          Pegá un link arriba para empezar. El primero puede tardar unos minutos.
        </p>
      </div>
    );
  }

  return (
    <>
      <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-dim)" }}>
        Tus videos ({videos.length})
      </h2>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {videos.map((video) => {
          const stage = STAGES[video.status] || STAGES.pending;
          const active = !["completed", "error"].includes(video.status);
          const duration = formatDuration(video.duration_seconds);

          return (
            <article
              key={video.id}
              onClick={() => onOpen(video)}
              className="card card-interactive group overflow-hidden"
            >
              <div className="relative aspect-video overflow-hidden" style={{ background: "var(--bg)" }}>
                {video.thumbnail_url ? (
                  <img
                    src={video.thumbnail_url}
                    alt=""
                    loading="lazy"
                    // Older rows hold expired signed URLs; fall back to the
                    // placeholder rather than showing a broken image icon.
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                    className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-2xl opacity-30">
                    🎬
                  </div>
                )}

                {duration && (
                  <span
                    className="absolute bottom-2 right-2 rounded px-1.5 py-0.5 text-xs font-medium"
                    style={{ background: "rgba(0,0,0,0.78)", color: "#fff" }}
                  >
                    {duration}
                  </span>
                )}
              </div>

              <div className="p-4">
                <h3 className="mb-2 line-clamp-2 text-sm font-semibold leading-snug">
                  {video.title || "Sin título"}
                </h3>

                <div className="mb-2.5 flex items-center gap-2">
                  <span className="chip" style={{ background: "var(--bg)", color: stage.tone }}>
                    {active && (
                      <span
                        className="pulse-dot h-1.5 w-1.5 rounded-full"
                        style={{ background: stage.tone }}
                      />
                    )}
                    {stage.label}
                  </span>
                  {active && (
                    <span className="text-xs" style={{ color: "var(--text-faint)" }}>
                      {Math.round(video.processing_progress)}%
                    </span>
                  )}
                </div>

                {active && (
                  <div
                    className="relative mb-2.5 h-1 overflow-hidden rounded-full"
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
                )}

                {video.status === "error" && video.error_message && (
                  <p className="mb-2 line-clamp-2 text-xs" style={{ color: "var(--bad)" }}>
                    {video.error_message}
                  </p>
                )}

                <div className="flex items-center justify-between">
                  <span className="text-xs" style={{ color: "var(--text-faint)" }}>
                    {video.channel_name || ""}
                  </span>
                  <button
                    onClick={(e) => remove(video.id, e)}
                    className="text-xs opacity-0 transition-opacity group-hover:opacity-100"
                    style={{ color: "var(--text-faint)" }}
                  >
                    Eliminar
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}
