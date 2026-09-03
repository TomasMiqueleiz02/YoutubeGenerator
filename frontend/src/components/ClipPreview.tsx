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
  const [media, setMedia] = useState<{
    video_url: string | null;
    thumbnail_url: string | null;
  } | null>(null);
  const { updateClip } = useStore();

  useEffect(() => {
    if (!clip.file_path) return;
    apiClient
      .getClipMedia(clip.id)
      .then(setMedia)
      .catch(() => setMedia(null));
  }, [clip.id, clip.file_path]);

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
      {media?.video_url ? (
        <video
          src={media.video_url}
          poster={media.thumbnail_url || undefined}
          controls
          preload="metadata"
          className="w-full h-64 bg-black object-contain"
        />
      ) : media?.thumbnail_url ? (
        <img
          src={media.thumbnail_url}
          alt={clip.title || "Clip"}
          className="w-full h-48 object-cover"
        />
      ) : (
        <div className="w-full h-48 bg-gray-900 flex items-center justify-center text-gray-500 text-sm">
          {clip.file_path ? "Loading preview..." : "Media not available"}
        </div>
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
        <div className="flex gap-2 flex-wrap">
          {media?.video_url && (
            <a
              href={media.video_url}
              download={`clip-${clip.id}.mp4`}
              className="text-xs bg-orange-600 hover:bg-orange-500 px-2 py-1 rounded"
            >
              Download
            </a>
          )}
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
