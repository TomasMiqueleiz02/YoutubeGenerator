import json
import logging
from typing import Dict, List, Optional

import requests

from app.config import settings

# Reuse the prompt and schema from the API-backed finder so both paths select
# moments by the same rules and hand downstream code identical shapes.
from .moment_finder import SYSTEM_PROMPT, MomentSelection

logger = logging.getLogger(__name__)


class LocalMomentFinder:
    """
    Picks clip-worthy moments with a language model running on this machine.

    Same job as MomentFinder, without a metered API: Ollama serves the model
    from local VRAM, so selection stays automatic and unattended. Quality sits
    below a frontier model but above keyword heuristics, because the model
    reads what is actually said rather than matching phrases from a list.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        timeout: int = 300,
    ):
        self.model = model or settings.LOCAL_LLM_MODEL
        self.host = (host or settings.LOCAL_LLM_HOST).rstrip("/")
        self.timeout = timeout

    @property
    def available(self) -> bool:
        """True when Ollama is up and the configured model is pulled."""
        if not settings.LOCAL_LLM_ENABLED:
            return False
        try:
            response = requests.get("%s/api/tags" % self.host, timeout=3)
            response.raise_for_status()
            names = [m.get("name", "") for m in response.json().get("models", [])]
            # Ollama reports "qwen2.5:7b"; accept a bare name without the tag
            base = self.model.split(":")[0]
            return any(n == self.model or n.split(":")[0] == base for n in names)
        except Exception:
            return False

    @staticmethod
    def _normalize(text: str) -> str:
        return "".join(c for c in text.lower() if c.isalnum() or c.isspace()).split()

    def _reanchor(self, moments: List[Dict], segments: List[Dict]) -> List[Dict]:
        """
        Replace model-supplied timestamps by locating each hook in the transcript.

        A small model reads which line is the hook well and reports where it
        happens badly: measured against a real transcript its timestamps were
        off by two to six minutes, so clips were cut nowhere near the line
        their title promised. The hook text, on the other hand, is quoted
        almost verbatim. Searching for it turns the timestamp into something
        derived from the transcript instead of something the model invented.
        """
        from difflib import SequenceMatcher

        haystack = [
            (seg, self._normalize(seg.get("text") or "")) for seg in segments
        ]

        anchored: List[Dict] = []
        for moment in moments:
            needle = self._normalize(moment.get("hook") or "")
            if not needle:
                continue

            best_score, best_seg = 0.0, None
            for seg, words in haystack:
                if not words:
                    continue
                score = SequenceMatcher(None, needle, words).ratio()
                if score > best_score:
                    best_score, best_seg = score, seg

            if best_seg is None or best_score < 0.4:
                logger.info(
                    "Could not locate hook in transcript (best %.2f): %s",
                    best_score,
                    (moment.get("hook") or "")[:60],
                )
                continue

            length = moment["end"] - moment["start"]
            start = float(best_seg["start"])
            moment = dict(moment)
            moment["start"] = start
            moment["end"] = start + length
            anchored.append(moment)

        return anchored

    def find(
        self,
        transcript_text: str,
        video_duration: float,
        video_title: Optional[str] = None,
        max_clips: int = 10,
        segments: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Return chosen moments, or an empty list so the caller falls back.

        Long transcripts are processed in windows: an hour of speech runs well
        past a local model's context, and feeding it everything at once either
        truncates silently or times out. Each window is judged on its own and
        the results compete at the end.

        Never raises: a local model failing should degrade to heuristics, not
        take down the job.
        """
        if not transcript_text.strip():
            return []

        lines = transcript_text.splitlines()
        windows = self._split(lines)

        if len(windows) == 1:
            moments = self._ask(windows[0], video_duration, video_title, max_clips)
        else:
            logger.info("Transcript split into %d windows", len(windows))
            # Ask each window for fewer clips than the final target; the best
            # across all of them are kept after they compete on score.
            per_window = max(2, (max_clips // len(windows)) + 1)
            moments = []
            for index, window in enumerate(windows, 1):
                found = self._ask(window, video_duration, video_title, per_window)
                logger.info("Window %d/%d yielded %d", index, len(windows), len(found))
                moments.extend(found)

        cleaned = self._sanitize(moments, video_duration)

        # Trust the model on which line is the hook, not on when it happens.
        if segments:
            cleaned = self._reanchor(cleaned, segments)
            # Re-resolve overlaps: moving clips can push two onto each other.
            cleaned.sort(key=lambda m: m["score"], reverse=True)
            kept: List[Dict] = []
            for candidate in cleaned:
                if not any(
                    candidate["start"] < k["end"] and candidate["end"] > k["start"]
                    for k in kept
                ):
                    kept.append(candidate)
            cleaned = kept

        return cleaned[:max_clips]

    def _split(self, lines: List[str], max_chars: int = 9000) -> List[str]:
        """Group transcript lines into windows small enough for the context."""
        windows: List[str] = []
        current: List[str] = []
        size = 0

        for line in lines:
            if size + len(line) > max_chars and current:
                windows.append("\n".join(current))
                current, size = [], 0
            current.append(line)
            size += len(line) + 1

        if current:
            windows.append("\n".join(current))
        return windows or [""]

    def _ask(
        self,
        transcript_text: str,
        video_duration: float,
        video_title: Optional[str],
        max_clips: int,
    ):
        """One request against one window. Returns raw Moment objects."""
        # A 7B model follows the system prompt loosely, so the constraints that
        # matter most are restated here, next to the data it is judging.
        user_content = (
            "Video title: %s\n"
            "Video duration: %d seconds\n"
            "Return at most %d clips.\n\n"
            "Requirements, all mandatory:\n"
            "- score is an integer from 0 to 100, not 0 to 10. A clip you would "
            "genuinely post scores above 70; filler scores below 40.\n"
            "- Every clip must last between 15 and 60 seconds.\n"
            "- Skip lines that only announce where they are or what they are "
            "about to do. Those set up a clip, they are not one.\n"
            "- Pick the line where something is revealed, claimed, or reacted "
            "to, and run until that idea closes.\n\n"
            "Transcript:\n%s"
            % (video_title or "unknown", int(video_duration), max_clips, transcript_text)
        )

        try:
            response = requests.post(
                "%s/api/chat" % self.host,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    # Constrained decoding against the same schema the API path
                    # validates, so the model cannot return unparseable output.
                    "format": MomentSelection.model_json_schema(),
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # selection, not creative writing
                        "num_ctx": 8192,     # sized to one window, not the film
                    },
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            if not content:
                return []

            return MomentSelection.model_validate(json.loads(content)).moments

        except Exception:
            logger.exception("Local model window failed")
            return []

    def _sanitize(self, moments, video_duration: float) -> List[Dict]:
        """
        Drop moments that break timing rules and resolve overlaps.

        Mirrors MomentFinder._sanitize: a smaller model needs this more, not
        less, since it is likelier to invent a timestamp past the end.
        """
        raw_scores = [int(m.score) for m in moments] or [0]
        # Small models routinely answer on a 1-10 scale no matter what the
        # schema says. If nothing exceeds 10, read it as 0-10 and rescale
        # rather than presenting every clip as a single-digit score.
        rescale = max(raw_scores) <= 10

        cleaned: List[Dict] = []

        for moment in moments:
            start = max(0.0, float(moment.start_seconds))
            end = float(moment.end_seconds)
            if video_duration:
                end = min(end, float(video_duration))

            duration = end - start
            if duration < 12:
                continue
            if duration > 60:
                # Overruns are common and usually mean the model kept going
                # past the payoff. Trim to the cap instead of discarding a
                # moment that started in the right place.
                end = start + 60
                duration = 60

            score = int(moment.score)
            if rescale:
                score *= 10

            cleaned.append(
                {
                    "start": start,
                    "end": end,
                    "title": moment.title,
                    "hook": moment.hook,
                    "reason": moment.reason,
                    "score": max(0, min(100, score)),
                }
            )

        cleaned.sort(key=lambda m: m["score"], reverse=True)
        kept: List[Dict] = []
        for candidate in cleaned:
            overlaps = any(
                candidate["start"] < k["end"] and candidate["end"] > k["start"]
                for k in kept
            )
            if not overlaps:
                kept.append(candidate)

        return kept
