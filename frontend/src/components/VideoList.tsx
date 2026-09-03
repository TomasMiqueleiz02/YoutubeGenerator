import { useEffect } from "react";
import { useStore } from "../store/useStore";
import { apiClient } from "../services/api";
import { Video } from "../types";

interface Props {
  onVideoSelected: (video: Video) => void;
}

export default function VideoList({ onVideoSelected }: Props) {
  const { videos, setVideos, setLoading, setError } = useStore();

  useEffect(() => {
    loadVideos();
  }, []);

  const loadVideos = async () => {
    setLoading(true);
    try {
      const result = await apiClient.listVideos();
      setVideos(result.videos);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load videos");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (videoId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiClient.deleteVideo(videoId);
      setVideos(videos.filter((v) => v.id !== videoId));
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to delete video");
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: "bg-gray-600",
      downloading: "bg-blue-600",
      processing: "bg-purple-600",
      analyzed: "bg-indigo-600",
      completed: "bg-green-600",
      error: "bg-red-600",
    };
    return colors[status] || "bg-gray-600";
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {videos.map((video) => (
        <div
          key={video.id}
          onClick={() => onVideoSelected(video)}
          className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700 hover:border-orange-500 cursor-pointer transition-colors"
        >
          {video.thumbnail_url && (
            <img
              src={video.thumbnail_url}
              alt={video.title}
              className="w-full h-40 object-cover"
            />
          )}
          <div className="p-4">
            <h3 className="font-bold text-white line-clamp-2 mb-2">
              {video.title || "Untitled"}
            </h3>
            <p className="text-sm text-gray-400 mb-3">
              {video.channel_name || "Unknown channel"}
            </p>
            <div className="mb-3">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span className={`${getStatusColor(video.status)} px-2 py-1 rounded text-white text-xs font-semibold`}>
                  {video.status}
                </span>
                <span>{video.processing_progress}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className="bg-orange-500 h-2 rounded-full transition-all"
                  style={{ width: `${video.processing_progress}%` }}
                ></div>
              </div>
            </div>
            {video.error_message && (
              <p className="text-xs text-red-400 mb-2">{video.error_message}</p>
            )}
            <button
              onClick={(e) => handleDelete(video.id, e)}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
