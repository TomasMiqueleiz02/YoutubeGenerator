import warnings

import numpy as np
import librosa

from .audio_extract import extracted_audio

warnings.filterwarnings("ignore")


class AudioAnalyzer:
    """Analyzes audio to detect high energy / high emotion moments."""

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.sr = 22050  # sample rate
        self.hop_length = 512
        self.y = None

    def analyze(self) -> np.ndarray:
        """Analyzes audio and returns a timeline of scores, one per second."""
        # soundfile cannot open MP4, so pull the audio out first
        with extracted_audio(self.video_path, self.sr) as wav_path:
            self.y, self.sr = librosa.load(wav_path, sr=self.sr)

        if self.y is None or len(self.y) == 0:
            return np.array([], dtype=float)

        energy_score = self._get_energy_score()
        onset_score = self._get_onset_score()
        tempo_score = self._get_tempo_score()
        spectral_score = self._get_spectral_score()

        length = min(
            len(energy_score), len(onset_score), len(tempo_score), len(spectral_score)
        )

        combined = (
            0.35 * energy_score[:length]
            + 0.30 * onset_score[:length]
            + 0.20 * tempo_score[:length]
            + 0.15 * spectral_score[:length]
        )

        combined_per_second = self._frames_to_seconds(combined)
        return np.clip(combined_per_second, 0, 100)

    def _get_energy_score(self) -> np.ndarray:
        """Detects energy level (amplitude)."""
        rms = librosa.feature.rms(y=self.y, hop_length=self.hop_length)[0]
        return self._normalize(rms)

    def _get_onset_score(self) -> np.ndarray:
        """Detects abrupt changes (onsets)."""
        onset_env = librosa.onset.onset_strength(
            y=self.y, sr=self.sr, hop_length=self.hop_length
        )
        return self._normalize(onset_env)

    def _get_tempo_score(self) -> np.ndarray:
        """Detects tempo and rhythm changes."""
        onset_env = librosa.onset.onset_strength(
            y=self.y, sr=self.sr, hop_length=self.hop_length
        )
        tempogram = librosa.feature.tempogram(
            onset_envelope=onset_env, sr=self.sr, hop_length=self.hop_length
        )
        tempo_score = np.sum(tempogram, axis=0)
        return self._normalize(tempo_score)

    def _get_spectral_score(self) -> np.ndarray:
        """Detects spectral (timbre) changes."""
        spectral_centroid = librosa.feature.spectral_centroid(
            y=self.y, sr=self.sr, hop_length=self.hop_length
        )[0]
        spectral_diff = np.abs(np.diff(spectral_centroid, prepend=spectral_centroid[0]))
        return self._normalize(spectral_diff)

    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        """Normalize to 0-100."""
        arr = np.asarray(arr, dtype=float)
        if len(arr) == 0:
            return arr
        min_v, max_v = np.min(arr), np.max(arr)
        if max_v == min_v:
            return np.full_like(arr, 50, dtype=float)
        return ((arr - min_v) / (max_v - min_v)) * 100

    def _frames_to_seconds(self, data: np.ndarray) -> np.ndarray:
        """Convert per-frame data to per-second data."""
        target_length = max(int(len(self.y) / self.sr), 1)
        frame_times = librosa.frames_to_time(
            np.arange(len(data)), sr=self.sr, hop_length=self.hop_length
        )
        return np.interp(np.arange(target_length), frame_times, data)
