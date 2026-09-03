import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Transcriber:
    """
    Speech-to-text with word-level timing.

    Uses faster-whisper (CTranslate2) rather than openai-whisper: same models,
    a fraction of the memory, and no torch dependency, which matters on a
    container with a modest memory ceiling.
    """

    def __init__(self, model_size: str = "base", language: Optional[str] = None):
        self.model_size = model_size
        self.language = language
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            # int8 on CPU keeps memory low enough for a small container
            self._model = WhisperModel(
                self.model_size, device="cpu", compute_type="int8"
            )
        return self._model

    def transcribe(self, media_path: str) -> Dict:
        """
        Return the transcript as segments with start/end timestamps.

        Shape: {"language": str, "duration": float, "segments": [
            {"start": float, "end": float, "text": str}, ...
        ]}
        """
        model = self._load()

        segments_iter, info = model.transcribe(
            media_path,
            language=self.language,
            vad_filter=True,  # skip silence, keeps timestamps honest
            beam_size=1,      # greedy: much faster, accurate enough for clipping
        )

        segments: List[Dict] = []
        for segment in segments_iter:
            text = (segment.text or "").strip()
            if not text:
                continue
            segments.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": text,
                }
            )

        logger.info(
            "Transcribed %s: %d segments, language=%s",
            media_path,
            len(segments),
            getattr(info, "language", None),
        )

        return {
            "language": getattr(info, "language", None),
            "duration": float(getattr(info, "duration", 0.0)),
            "segments": segments,
        }

    @staticmethod
    def to_timestamped_text(transcript: Dict, max_chars: int = 120000) -> str:
        """
        Flatten segments into "[mm:ss] text" lines for a language model.

        Timestamps are inline so the model can cite exact moments back. Long
        transcripts are truncated at a segment boundary rather than mid-line.
        """
        lines: List[str] = []
        used = 0

        for segment in transcript.get("segments", []):
            start = int(segment["start"])
            stamp = "[%02d:%02d]" % (start // 60, start % 60)
            line = "%s %s" % (stamp, segment["text"])
            if used + len(line) > max_chars:
                lines.append("[transcript truncated]")
                break
            lines.append(line)
            used += len(line) + 1

        return "\n".join(lines)
