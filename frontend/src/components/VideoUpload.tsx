import { useState } from "react";
import { useStore } from "../store/useStore";
import { apiClient } from "../services/api";

export default function VideoUpload() {
  const { addVideo } = useStore();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setError(null);
    setLoading(true);
    try {
      addVideo(await apiClient.createVideo(url.trim()));
      setUrl("");
    } catch (err: any) {
      const detail = err.response?.data?.detail || "";
      // Surface the common failures in plain language instead of a stack of
      // yt-dlp jargon the user cannot act on.
      if (/bot|sign in|cookies/i.test(detail)) {
        setError(
          "YouTube bloqueó la descarga. Revisá que el worker esté corriendo en tu PC."
        );
      } else if (/already exists/i.test(detail)) {
        setError("Ese video ya está en tu lista.");
      } else if (/unavailable|private|not found/i.test(detail)) {
        setError("El video no está disponible o es privado.");
      } else {
        setError(detail.slice(0, 160) || "No se pudo agregar el video.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="mb-10">
      <h1 className="mb-1 text-2xl font-bold tracking-tight">Nuevo video</h1>
      <p className="mb-4 text-sm" style={{ color: "var(--text-dim)" }}>
        Pegá un link de YouTube y te devuelvo los mejores momentos, ya cortados
        en vertical y con subtítulos.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-2.5 sm:flex-row">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          className="input flex-1"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="btn btn-primary sm:w-40"
        >
          {loading ? "Agregando..." : "Generar clips"}
        </button>
      </form>

      {error && (
        <div
          className="mt-3 rounded-lg px-3.5 py-2.5 text-sm"
          style={{ background: "rgba(248,113,113,0.1)", color: "var(--bad)" }}
        >
          {error}
        </div>
      )}
    </section>
  );
}
