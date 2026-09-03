import { useState } from "react";
import { useStore } from "../store/useStore";
import VideoList from "./VideoList";
import ClipPreview from "./ClipPreview";
import VideoUpload from "./VideoUpload";
import { Video } from "../types";

export default function Dashboard() {
  const {
    videos,
    selectedVideo,
    setSelectedVideo,
    clips,
    setVideos,
    setClips,
  } = useStore();
  const [tab, setTab] = useState<"videos" | "clips">("videos");

  const handleVideoSelected = async (video: Video) => {
    setSelectedVideo(video);
    setTab("clips");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-white p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold">YouTube Clip Generator</h1>
          <div className="text-sm text-gray-400">
            {videos.length} videos • {clips.length} clips
          </div>
        </div>

        <div className="flex gap-4 mb-8 border-b border-gray-700">
          <button
            onClick={() => setTab("videos")}
            className={`px-4 py-2 font-semibold transition-colors ${
              tab === "videos"
                ? "text-orange-500 border-b-2 border-orange-500"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Videos
          </button>
          <button
            onClick={() => setTab("clips")}
            className={`px-4 py-2 font-semibold transition-colors ${
              tab === "clips"
                ? "text-orange-500 border-b-2 border-orange-500"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Clips {selectedVideo ? `(${selectedVideo.title || "Untitled"})` : ""}
          </button>
        </div>

        {tab === "videos" && (
          <div className="space-y-6">
            <VideoUpload />
            <VideoList onVideoSelected={handleVideoSelected} />
          </div>
        )}

        {tab === "clips" && selectedVideo && (
          <ClipPreview video={selectedVideo} />
        )}

        {tab === "clips" && !selectedVideo && (
          <div className="text-center py-12 text-gray-400">
            <p>Select a video to view its clips</p>
          </div>
        )}
      </div>
    </div>
  );
}
