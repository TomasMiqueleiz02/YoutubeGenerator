import logging
import os

import numpy as np
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

    @staticmethod
    def _register_cuda_libraries() -> None:
        """
        Put the pip-installed CUDA DLLs where Windows will find them.

        nvidia-cublas-cu12 and nvidia-cudnn-cu12 drop their DLLs inside
        site-packages, which is not on the DLL search path. Without this the
        model constructs fine and then fails at the first encode call with a
        missing cublas64_12.dll.
        """
        if os.name != "nt":
            return
        try:
            import site

            roots = list(site.getsitepackages())
            user_site = site.getusersitepackages()
            if isinstance(user_site, str):
                roots.append(user_site)

            for root in roots:
                nvidia_root = os.path.join(root, "nvidia")
                if not os.path.isdir(nvidia_root):
                    continue
                for dirpath, dirnames, _files in os.walk(nvidia_root):
                    if os.path.basename(dirpath) == "bin":
                        os.add_dll_directory(dirpath)
        except Exception:
            # Not fatal: the CPU path still works
            logger.debug("Could not register CUDA DLL directories", exc_info=True)

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            # Prefer the GPU: it makes a larger, more accurate model cheaper
            # than a small one on CPU, and transcript quality is what clip
            # selection reads. Verified with a real encode, because building
            # the model succeeds even when the CUDA runtime is missing.
            self._register_cuda_libraries()
            try:
                model = WhisperModel(
                    self.model_size, device="cuda", compute_type="float16"
                )
                model.encode(
                    np.zeros(
                        (model.feature_extractor.n_mels, 3000), dtype=np.float32
                    )
                )
                self._model = model
                logger.info("Whisper %s running on GPU", self.model_size)
            except Exception as exc:
                logger.info(
                    "GPU unavailable for Whisper (%s); using CPU",
                    str(exc)[:120],
                )
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
            vad_filter=True,       # skip silence, keeps timestamps honest
            beam_size=1,           # greedy: much faster, accurate enough here
            word_timestamps=True,  # required for word-by-word captions
        )

        segments: List[Dict] = []
        for segment in segments_iter:
            text = (segment.text or "").strip()
            if not text:
                continue

            words = []
            for word in (getattr(segment, "words", None) or []):
                token = (word.word or "").strip()
                if token:
                    words.append(
                        {
                            "start": float(word.start),
                            "end": float(word.end),
                            "text": token,
                        }
                    )

            segments.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": text,
                    "words": words,
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
    def merge_segments(
        segments: List[Dict], max_gap: float = 1.2, max_duration: float = 30.0
    ) -> List[Dict]:
        """
        Join consecutive segments into continuous blocks of speech.

        Whisper splits on breath and pause, so conversational audio comes back
        as a stream of three-word fragments: "no, nothing", "there we go",
        "is it good?". A model reading those sees debris and cannot tell where
        an idea starts or ends. Merging across short gaps rebuilds paragraphs,
        which is the shape the selection prompt is written for.

        Blocks are cut at a long pause or once they run long enough that they
        would no longer fit inside a clip.
        """
        merged: List[Dict] = []

        for segment in segments:
            text = (segment.get("text") or "").strip()
            if not text:
                continue

            if merged:
                previous = merged[-1]
                gap = float(segment["start"]) - float(previous["end"])
                span = float(segment["end"]) - float(previous["start"])
                if gap <= max_gap and span <= max_duration:
                    previous["end"] = float(segment["end"])
                    previous["text"] = "%s %s" % (previous["text"], text)
                    continue

            merged.append(
                {
                    "start": float(segment["start"]),
                    "end": float(segment["end"]),
                    "text": text,
                }
            )

        return merged

    @staticmethod
    def to_timestamped_text(transcript: Dict, max_chars: int = 120000) -> str:
        """
        Flatten segments into "[mm:ss] text" lines for a language model.

        Timestamps are inline so the model can cite exact moments back. Long
        transcripts are truncated at a segment boundary rather than mid-line.
        """
        lines: List[str] = []
        used = 0

        # Read merged blocks rather than raw fragments; see merge_segments.
        for segment in Transcriber.merge_segments(transcript.get("segments", [])):
            start = int(segment["start"])
            stamp = "[%02d:%02d]" % (start // 60, start % 60)
            line = "%s %s" % (stamp, segment["text"])
            if used + len(line) > max_chars:
                lines.append("[transcript truncated]")
                break
            lines.append(line)
            used += len(line) + 1

        return "\n".join(lines)
