import { useEffect, useState } from "react";
import { useStore } from "../store/useStore";
import { apiClient } from "../services/api";
import { Video } from "../types";

interface Props {
  video: Video;
}

export default function ClipPreview({ video }: Props) {
  const { clips, setClips } = useStore();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadClips();
  }, [video.id]);

  const loadClips = async () => {
    setLoading(true);
    try {
      const result = await apiClient.getClipsForVideo(video.id);
      setClips(result.clips);
    } catch (err) {
      console.error("Failed to load clips", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-12">Loading clips...</div>;
  }

  if (clips.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <p>No clips generated yet</p>
        <p className="text-sm mt-2">
          {video.status === "completed"
            ? "Clips should appear shortly"
            : `Video is still ${video.status}`}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold mb-4">Generated Clips</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {clips.map((clip) => (
          <ClipCard key={clip.id} clip={clip} onRefresh={loadClips} />
        ))}
      </div>
    </div>
  );
}

function ClipCard({ clip, onRefresh }: any) {
  const [publishing, setPublishing] = useState<string | null>(null);
  const { updateClip } = useStore();

  const handlePublish = async (platform: "tiktok" | "instagram" | "youtube") => {
    setPublishing(platform);
    try {
      let result;
      if (platform === "tiktok") {
        result = await apiClient.publishToTikTok(clip.id);
      } else if (platform === "instagram") {
        result = await apiClient.publishToInstagram(clip.id);
      } else {
        result = await apiClient.publishToYoutube(clip.id);
      }

      updateClip({
        ...clip,
        published_platforms: [...clip.published_platforms, platform],
        status: "published",
      });
    } catch (err: any) {
      console.error(`Failed to publish to ${platform}:`, err);
    } finally {
      setPublishing(null);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
      {clip.thumbnail_path && (
        <img
          src={clip.thumbnail_path}
          alt={clip.title || "Clip"}
          className="w-full h-48 object-cover"
        />
      )}
      <div className="p-4">
        <h3 className="font-bold mb-2">
          {clip.start_time.toFixed(1)}s - {clip.end_time.toFixed(1)}s
        </h3>
        {clip.title && <p className="text-sm mb-2">{clip.title}</p>}
        <div className="mb-3 space-y-1 text-sm">
          <p>
            Virality: <span className="font-bold text-orange-400">{clip.virality_score?.toFixed(0)}%</span>
          </p>
          <p>Audio: {clip.audio_score?.toFixed(0)}% | Video: {clip.video_score?.toFixed(0)}%</p>
        </div>
        <div className="flex gap-2">
          {!clip.published_platforms?.includes("tiktok") && (
            <button
              onClick={() => handlePublish("tiktok")}
              disabled={publishing === "tiktok"}
              className="text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded disabled:opacity-50"
            >
              TikTok
            </button>
          )}
          {!clip.published_platforms?.includes("instagram") && (
            <button
              onClick={() => handlePublish("instagram")}
              disabled={publishing === "instagram"}
              className="text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded disabled:opacity-50"
            >
              Instagram
            </button>
          )}
          {!clip.published_platforms?.includes("youtube_shorts") && (
            <button
              onClick={() => handlePublish("youtube")}
              disabled={publishing === "youtube"}
              className="text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded disabled:opacity-50"
            >
              YouTube
            </button>
          )}
        </div>
        {clip.published_platforms?.length > 0 && (
          <p className="text-xs text-green-400 mt-2">
            Published on: {clip.published_platforms.join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}
