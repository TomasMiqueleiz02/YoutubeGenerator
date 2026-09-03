import numpy as np
import whisper
from transformers import pipeline
from typing import Dict, List, Optional

# Words that tend to mark engaging or surprising moments
VIRAL_KEYWORDS = [
    "crazy", "amazing", "wait", "omg", "never", "actually", "literally",
    "shocked", "believe", "plot twist", "happens", "revealed",
    "shocking", "unbelievable", "incredible", "insane", "wild",
    "thought", "realized", "found out", "discovered", "secret",
]


class ContentAnalyzer:
    """Analyzes transcription, sentiment and keywords."""

    def __init__(
        self,
        video_path: str,
        whisper_model: str = "base",
        language: Optional[str] = None,
    ):
        self.video_path = video_path
        self.language = language
        self.whisper_model = whisper.load_model(whisper_model)
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
        )
        self.transcription: Optional[Dict] = None

    def analyze(self) -> np.ndarray:
        """Analyzes content and returns a timeline of scores, one per second."""
        self._transcribe()

        segments = self.transcription.get("segments", []) if self.transcription else []
        if not segments:
            return np.array([], dtype=float)

        duration = self._total_duration(segments)

        sentiment_score = self._get_sentiment_score(segments)
        keyword_score = self._get_keyword_score(segments)
        speech_rate_score = self._get_speech_rate_score(segments)

        combined_per_segment = (
            0.40 * sentiment_score + 0.40 * keyword_score + 0.20 * speech_rate_score
        )

        timeline = self._expand_to_duration(combined_per_segment, segments, duration)
        return np.clip(timeline, 0, 100)

    def get_transcript_text(self) -> str:
        """Full transcript text, useful for captions and titles."""
        if not self.transcription:
            return ""
        return self.transcription.get("text", "").strip()

    def get_segments(self) -> List[Dict]:
        if not self.transcription:
            return []
        return self.transcription.get("segments", [])

    def _transcribe(self):
        """Transcribe audio using Whisper."""
        kwargs = {}
        if self.language:
            kwargs["language"] = self.language
        self.transcription = self.whisper_model.transcribe(self.video_path, **kwargs)

    def _total_duration(self, segments: List[Dict]) -> float:
        if not segments:
            return 0.0
        return float(segments[-1].get("end", 0.0))

    def _get_sentiment_score(self, segments: List[Dict]) -> np.ndarray:
        """Score sentiment intensity per segment."""
        scores = []
        for segment in segments:
            text = segment.get("text", "")
            if len(text.strip()) < 5:
                scores.append(50.0)
                continue

            result = self.sentiment_pipeline(text[:512])[0]
            confidence = float(result["score"])
            # Strong sentiment in either direction is engaging
            scores.append(50.0 + confidence * 50.0)

        return np.array(scores, dtype=float)

    def _get_keyword_score(self, segments: List[Dict]) -> np.ndarray:
        """Detect words that typically drive engagement."""
        scores = []
        for segment in segments:
            text = segment.get("text", "").lower()
            keyword_count = sum(1 for kw in VIRAL_KEYWORDS if kw in text)
            scores.append(float(min(50 + keyword_count * 10, 100)))
        return np.array(scores, dtype=float)

    def _get_speech_rate_score(self, segments: List[Dict]) -> np.ndarray:
        """Detect changes in speaking pace."""
        scores = []
        prev_rate = None

        for segment in segments:
            text = segment.get("text", "")
            duration = float(segment.get("end", 0)) - float(segment.get("start", 0))

            if duration <= 0:
                scores.append(50.0)
                continue

            speech_rate = len(text.split()) / duration
            if prev_rate is not None:
                rate_change = abs(speech_rate - prev_rate) / (prev_rate + 0.01)
                scores.append(float(min(50 + rate_change * 30, 100)))
            else:
                scores.append(50.0)
            prev_rate = speech_rate

        return np.array(scores, dtype=float)

    def _expand_to_duration(
        self, scores: np.ndarray, segments: List[Dict], total_duration: float
    ) -> np.ndarray:
        """Expand per-segment scores into one score per second."""
        target_length = max(int(total_duration), 1)
        timeline = np.full(target_length, 50.0, dtype=float)

        for idx, segment in enumerate(segments):
            if idx >= len(scores):
                break
            start = int(max(float(segment.get("start", 0)), 0))
            end = int(min(float(segment.get("end", 0)), target_length))
            if end > start:
                timeline[start:end] = scores[idx]

        return timeline
