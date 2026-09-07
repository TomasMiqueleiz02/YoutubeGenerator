import logging

import cv2
import numpy as np

from app import time_ranges

logger = logging.getLogger(__name__)


class VideoAnalyzer:
    """
    Analyzes video for scene cuts, motion and brightness changes.

    All three signals are computed in a single decode pass over sampled frames,
    which keeps analysis time roughly proportional to video length instead of
    three times that.
    """

    def __init__(self, video_path: str, sample_fps: float = 5.0, ranges=None):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.duration = self.total_frames / self.fps if self.fps else 0.0
        # Analyze at most sample_fps frames per second of source video
        self.sample_fps = min(sample_fps, self.fps) if self.fps else sample_fps
        self.frame_step = max(int(round(self.fps / self.sample_fps)), 1)
        # Spans marked as worth clipping. This pass is the slowest stage of
        # the whole pipeline, so skipping the rest of the file is where the
        # marked spans pay for themselves: seek to each one instead of
        # decoding an hour of footage to look at ten minutes of it.
        self.ranges = time_ranges.normalize(ranges, self.duration)

    def analyze(self) -> np.ndarray:
        """Analyzes the video and returns a timeline of scores, one per second."""
        cut_scores, motion_scores, brightness_scores, timestamps = self._single_pass()

        if len(timestamps) == 0:
            return np.array([], dtype=float)

        combined = (
            0.50 * self._normalize(cut_scores)
            + 0.35 * self._normalize(motion_scores)
            + 0.15 * self._normalize(brightness_scores)
        )

        per_second = self._resample_to_seconds(combined, timestamps)
        return np.clip(per_second, 0, 100)

    def _spans(self):
        """Frame ranges to decode, as (first, last) inclusive."""
        last_frame = (self.total_frames - 1) if self.total_frames else None
        if not self.ranges:
            return [(0, last_frame)]

        spans = []
        for start, end in self.ranges:
            first = int(start * self.fps)
            stop = int(end * self.fps)
            if last_frame is not None:
                stop = min(stop, last_frame)
            spans.append((first, stop))
        return spans

    def _single_pass(self):
        """Decode once, computing scene-cut, motion and brightness signals."""
        cut_scores, motion_scores, brightness_scores, timestamps = [], [], [], []

        spans = self._spans()
        # Progress is reported against what will actually be decoded, which
        # is not the length of the file once spans are in play.
        to_decode = sum(
            (last - first + 1) for first, last in spans if last is not None
        ) or self.total_frames
        decoded = 0

        for first, last in spans:
            # Each span starts cold: comparing the first frame after a seek
            # against the last frame before it would invent a scene cut at
            # every seam.
            prev_gray = None
            prev_brightness = None

            if first:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, first)
                # Seeking lands on a keyframe, not necessarily the frame
                # asked for, so read back where we actually are rather than
                # assuming, or every timestamp in the span drifts.
                frame_index = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES) or first)
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_index = 0

            while last is None or frame_index <= last:
                # Only one frame in frame_step is measured. grab() advances
                # the decoder without converting and copying the pixels of
                # the ones in between, which is wasted work on the stage that
                # already dominates the run time.
                if frame_index % self.frame_step != 0:
                    if not self.cap.grab():
                        break
                    frame_index += 1
                    decoded += 1
                    continue

                ret, frame = self.cap.read()
                if not ret:
                    break

                decoded += 1

                frame = cv2.resize(frame, (320, 240))  # downscale for speed
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                brightness = float(np.mean(gray))

                if prev_gray is not None:
                    # Scene cut: histogram distance between consecutive frames
                    hist_curr = cv2.calcHist([gray], [0], None, [256], [0, 256])
                    hist_prev = cv2.calcHist([prev_gray], [0], None, [256], [0, 256])
                    cv2.normalize(hist_curr, hist_curr)
                    cv2.normalize(hist_prev, hist_prev)
                    cut = cv2.compareHist(hist_curr, hist_prev, cv2.HISTCMP_BHATTACHARYYA)
                    cut_scores.append(min(cut * 100, 100))

                    # Motion: dense optical flow magnitude
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                    )
                    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    motion_scores.append(float(min(np.mean(mag), 100)))

                    # Brightness delta
                    brightness_scores.append(
                        abs(brightness - prev_brightness) / 255.0 * 100.0
                    )
                else:
                    cut_scores.append(0.0)
                    motion_scores.append(0.0)
                    brightness_scores.append(0.0)

                timestamps.append(frame_index / self.fps if self.fps else 0.0)
                prev_gray = gray
                prev_brightness = brightness
                frame_index += 1

                # This pass is the slowest stage and otherwise silent, which
                # makes a long video look like a hung job.
                if to_decode and len(timestamps) % 200 == 0:
                    logger.info(
                        "Video analysis %.0f%% (%d of ~%d frames)",
                        100.0 * decoded / to_decode,
                        decoded,
                        to_decode,
                    )

        return (
            np.array(cut_scores),
            np.array(motion_scores),
            np.array(brightness_scores),
            np.array(timestamps),
        )

    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        if len(arr) == 0:
            return arr
        min_v, max_v = np.min(arr), np.max(arr)
        if max_v == min_v:
            return np.full_like(arr, 50, dtype=float)
        return ((arr - min_v) / (max_v - min_v)) * 100

    def _resample_to_seconds(self, data: np.ndarray, timestamps: np.ndarray) -> np.ndarray:
        """Convert sampled-frame data to per-second data."""
        target_length = max(int(self.duration), 1)
        return np.interp(np.arange(target_length), timestamps, data)

    def release(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    def __del__(self):
        try:
            self.release()
        except Exception:
            pass
