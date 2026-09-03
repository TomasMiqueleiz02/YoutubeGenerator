export interface User {
  id: string;
  email: string;
  username: string;
  tiktok_token?: string;
  instagram_token?: string;
  youtube_token?: string;
  is_active: boolean;
}

export interface Video {
  id: string;
  youtube_url: string;
  youtube_video_id: string;
  title?: string;
  channel_name?: string;
  thumbnail_url?: string;
  duration_seconds?: number;
  status: "pending" | "downloading" | "processing" | "analyzed" | "completed" | "error";
  processing_progress: number;
  error_message?: string;
  created_at: string;
  updated_at?: string;
}

export interface Clip {
  id: string;
  video_id: string;
  start_time: number;
  end_time: number;
  duration: number;
  virality_score?: number;
  audio_score?: number;
  video_score?: number;
  content_score?: number;
  title?: string;
  caption?: string;
  status: "generated" | "edited" | "published" | "scheduled";
  published_platforms: string[];
  thumbnail_path?: string;
  file_path?: string;
  created_at: string;
  published_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}
