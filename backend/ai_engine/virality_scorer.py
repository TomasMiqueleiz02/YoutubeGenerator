import numpy as np
from scipy.signal import find_peaks
from typing import List, Tuple


class VitalityScorer:
    """
    Combines audio, video and content scores to detect viral moments in a video.
    """

    def __init__(self):
        self.audio_weight = 0.35
        self.video_weight = 0.35
        self.content_weight = 0.30
        self.smoothing_window = 2  # seconds
        self.min_clip_duration = 15
        self.max_clip_duration = 60
        self.virality_threshold = 70  # minimum score to be considered "viral"

    def calculate_combined_score(
        self,
        audio_timeline: np.ndarray,
        video_timeline: np.ndarray,
        content_timeline: np.ndarray,
    ) -> np.ndarray:
        """
        Combines the 3 analyses into a single virality score (0-100), one value
        per second. Timelines of differing lengths are aligned to the shortest.
        """
        audio_timeline = np.asarray(audio_timeline, dtype=float)
        video_timeline = np.asarray(video_timeline, dtype=float)
        content_timeline = np.asarray(content_timeline, dtype=float)

        length = min(len(audio_timeline), len(video_timeline), len(content_timeline))
        if length == 0:
            return np.array([], dtype=float)

        audio_norm = self._normalize(audio_timeline[:length])
        video_norm = self._normalize(video_timeline[:length])
        content_norm = self._normalize(content_timeline[:length])

        combined = (
            self.audio_weight * audio_norm
            + self.video_weight * video_norm
            + self.content_weight * content_norm
        )

        # Smooth to avoid false peaks
        smoothed = self._smooth_timeline(combined, self.smoothing_window)

        return np.clip(smoothed, 0, 100)

    def detect_clip_boundaries(
        self, virality_scores: np.ndarray, video_duration: float
    ) -> List[Tuple[float, float, float]]:
        """
        Detects where viral clips start and end.
        Returns a list of (start_time, end_time, virality_score) tuples.
        """
        virality_scores = np.asarray(virality_scores, dtype=float)
        if virality_scores.size == 0:
            return []

        peaks, _ = find_peaks(
            virality_scores,
            height=self.virality_threshold,
            distance=5,  # at least 5 seconds between peaks
        )

        clips: List[Tuple[float, float, float]] = []

        for peak_idx in peaks:
            start_idx = self._find_start_boundary(virality_scores, peak_idx)
            end_idx = self._find_end_boundary(
                virality_scores, peak_idx, len(virality_scores)
            )

            start_time = float(start_idx)
            end_time = float(end_idx)

            # Pad short windows out to the minimum clip length when there is room
            if end_time - start_time < self.min_clip_duration:
                deficit = self.min_clip_duration - (end_time - start_time)
                start_time = max(0.0, start_time - deficit / 2)
                end_time = min(float(video_duration or len(virality_scores)),
                               end_time + deficit / 2)

            # Trim over-long windows around the peak
            if end_time - start_time > self.max_clip_duration:
                end_time = start_time + self.max_clip_duration

            duration = end_time - start_time
            if self.min_clip_duration <= duration <= self.max_clip_duration:
                peak_score = float(virality_scores[peak_idx])
                clips.append((start_time, end_time, peak_score))

        clips = self._remove_overlaps(clips)
        clips.sort(key=lambda x: x[2], reverse=True)
        return clips

    def _remove_overlaps(
        self, clips: List[Tuple[float, float, float]]
    ) -> List[Tuple[float, float, float]]:
        """Keep the highest scoring clip whenever two windows overlap."""
        if not clips:
            return []
        ordered = sorted(clips, key=lambda x: x[2], reverse=True)
        kept: List[Tuple[float, float, float]] = []
        for start, end, score in ordered:
            if all(end <= k_start or start >= k_end for k_start, k_end, _ in kept):
                kept.append((start, end, score))
        return kept

    def _normalize(self, array: np.ndarray) -> np.ndarray:
        """Normalize an array to 0-100."""
        if len(array) == 0:
            return array
        min_val = np.min(array)
        max_val = np.max(array)
        if max_val == min_val:
            return np.full_like(array, 50, dtype=float)
        return ((array - min_val) / (max_val - min_val)) * 100

    def _smooth_timeline(self, timeline: np.ndarray, window_seconds: int) -> np.ndarray:
        """Apply gaussian smoothing. Timeline is one sample per second."""
        from scipy.ndimage import gaussian_filter1d

        sigma = max(window_seconds / 2.0, 0.5)
        return gaussian_filter1d(timeline, sigma=sigma)

    def _find_start_boundary(self, scores: np.ndarray, peak_idx: int) -> int:
        """Find the clip start (where the score begins to rise)."""
        threshold = scores[peak_idx] * 0.6
        for i in range(peak_idx, -1, -1):
            if scores[i] < threshold:
                return max(0, i + 1)
        return 0

    def _find_end_boundary(
        self, scores: np.ndarray, peak_idx: int, total_len: int
    ) -> int:
        """Find the clip end (where the score falls off)."""
        threshold = scores[peak_idx] * 0.6
        for i in range(peak_idx, total_len):
            if scores[i] < threshold:
                return min(total_len - 1, i)
        return total_len - 1
