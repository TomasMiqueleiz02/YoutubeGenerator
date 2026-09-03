import { useState } from "react";
import { useStore } from "../store/useStore";
import { apiClient } from "../services/api";

export default function VideoUpload() {
  const { addVideo, setError } = useStore();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    try {
      const video = await apiClient.createVideo(url);
      addVideo(video);
      setUrl("");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to upload video");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-xl font-bold mb-4">Add YouTube Video</h2>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          placeholder="Paste YouTube URL..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          className="flex-1 bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-orange-500"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="bg-orange-500 hover:bg-orange-600 disabled:opacity-50 px-6 py-2 rounded font-semibold transition-colors"
        >
          {loading ? "Processing..." : "Add Video"}
        </button>
      </form>
    </div>
  );
}
