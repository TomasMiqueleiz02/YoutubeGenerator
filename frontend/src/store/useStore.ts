import { create } from "zustand";
import { Clip, User, Video } from "../types";

interface StoreState {
  user: User | null;
  token: string | null;
  videos: Video[];
  clips: Clip[];
  selectedVideo: Video | null;
  loading: boolean;
  error: string | null;

  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setVideos: (videos: Video[]) => void;
  addVideo: (video: Video) => void;
  setClips: (clips: Clip[]) => void;
  addClip: (clip: Clip) => void;
  updateClip: (clip: Clip) => void;
  deleteClip: (clipId: string) => void;
  setSelectedVideo: (video: Video | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  logout: () => void;
}

export const useStore = create<StoreState>((set) => ({
  user: null,
  token: typeof localStorage !== "undefined" ? localStorage.getItem("token") : null,
  videos: [],
  clips: [],
  selectedVideo: null,
  loading: false,
  error: null,

  setUser: (user) => set({ user }),
  setToken: (token) => {
    if (token) {
      typeof localStorage !== "undefined" && localStorage.setItem("token", token);
    } else {
      typeof localStorage !== "undefined" && localStorage.removeItem("token");
    }
    set({ token });
  },
  setVideos: (videos) => set({ videos }),
  addVideo: (video) => set((state) => ({ videos: [video, ...state.videos] })),
  setClips: (clips) => set({ clips }),
  addClip: (clip) => set((state) => ({ clips: [clip, ...state.clips] })),
  updateClip: (clip) =>
    set((state) => ({
      clips: state.clips.map((c) => (c.id === clip.id ? clip : c)),
    })),
  deleteClip: (clipId) =>
    set((state) => ({ clips: state.clips.filter((c) => c.id !== clipId) })),
  setSelectedVideo: (video) => set({ selectedVideo: video }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  logout: () =>
    set({
      user: null,
      token: null,
      videos: [],
      clips: [],
      selectedVideo: null,
    }),
}));
