import axios, { AxiosInstance } from "axios";
import { Clip, Video, AuthResponse, User } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({ baseURL: API_URL });
    this.setupInterceptors();
  }

  private setupInterceptors() {
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem("token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  // Auth
  async register(email: string, username: string, password: string): Promise<User> {
    const res = await this.client.post("/auth/register", { email, username, password });
    return res.data;
  }

  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await this.client.post("/auth/login", { email, password });
    return res.data;
  }

  async getCurrentUser(): Promise<User> {
    const res = await this.client.get("/auth/me");
    return res.data;
  }

  // Videos
  async createVideo(youtubeUrl: string): Promise<Video> {
    const res = await this.client.post("/videos/", { youtube_url: youtubeUrl });
    return res.data;
  }

  async getVideo(videoId: string): Promise<Video> {
    const res = await this.client.get(`/videos/${videoId}`);
    return res.data;
  }

  async listVideos(skip: number = 0, limit: number = 10): Promise<{ videos: Video[]; total: number }> {
    const res = await this.client.get("/videos/", { params: { skip, limit } });
    return res.data;
  }

  async deleteVideo(videoId: string): Promise<void> {
    await this.client.delete(`/videos/${videoId}`);
  }

  // Clips
  async getClipsForVideo(videoId: string): Promise<{ clips: Clip[]; total: number }> {
    const res = await this.client.get(`/clips/video/${videoId}`);
    return res.data;
  }

  async getClip(clipId: string): Promise<Clip> {
    const res = await this.client.get(`/clips/${clipId}`);
    return res.data;
  }

  async updateClip(
    clipId: string,
    updates: Partial<Clip>
  ): Promise<Clip> {
    const res = await this.client.put(`/clips/${clipId}`, updates);
    return res.data;
  }

  async deleteClip(clipId: string): Promise<void> {
    await this.client.delete(`/clips/${clipId}`);
  }

  // Publish
  async publishToTikTok(clipId: string): Promise<{ status: string; post_id: string }> {
    const res = await this.client.post(`/publish/${clipId}/tiktok`);
    return res.data;
  }

  async publishToInstagram(clipId: string): Promise<{ status: string; post_id: string }> {
    const res = await this.client.post(`/publish/${clipId}/instagram`);
    return res.data;
  }

  async publishToYoutube(clipId: string): Promise<{ status: string; post_id: string }> {
    const res = await this.client.post(`/publish/${clipId}/youtube`);
    return res.data;
  }

  async getClipAnalytics(clipId: string): Promise<any> {
    const res = await this.client.get(`/publish/${clipId}/analytics`);
    return res.data;
  }
}

export const apiClient = new APIClient();
