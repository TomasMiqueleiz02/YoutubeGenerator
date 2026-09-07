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

    @staticmethod
    def _span(segments, index, moment, target=30.0, cap=60.0, floor=15.0):
        """
        Where the clip runs, measured off the transcript rather than the model.

        The model is asked for start and end in seconds and answers in
        whatever shape the timestamps in front of it happen to have. On a
        span that began at 52:00 it returned the minute column -- 52 to 52,
        54 to 55 -- so every moment came out zero seconds long and the entire
        selection was thrown away before anything could use it.

        Its numbers are used only when they describe a plausible clip.
        Otherwise the clip runs from the anchored line until an idea closes,
        which the merged segments already mark.
        """
        start = float(segments[index]["start"])

        proposed = float(moment.end_seconds) - float(moment.start_seconds)
        if floor <= proposed <= cap:
            return start, start + proposed

        end = float(segments[index]["end"])
        following = index + 1
        while end - start < target and following < len(segments):
            candidate = float(segments[following]["end"])
            if candidate - start > cap:
                break
            end = candidate
            following += 1

        return start, end

    def _anchor(self, moments, segments, video_duration: float) -> List[Dict]:
        """
        Rebuild each moment around where its hook actually appears.

        A small model reads which line is the hook well and reports where it
        happens badly: measured against a real transcript its timestamps were
        off by two to six minutes, so clips were cut nowhere near the line
        their title promised. The hook text, on the other hand, is quoted
        almost verbatim. Searching for it turns both ends of the clip into
        something derived from the transcript instead of something invented.
        """
        from difflib import SequenceMatcher

        haystack = [
            (index, self._normalize(seg.get("text") or ""))
            for index, seg in enumerate(segments)
        ]
        rescale = self._uses_small_scale(moments)

        anchored: List[Dict] = []
        for moment in moments:
            needle = self._normalize(moment.hook or "")
            if not needle:
                logger.info("Moment arrived without a hook to locate; dropped")
                continue

            best_score, best_index = 0.0, None
            for index, words in haystack:
                if not words:
                    continue
                score = SequenceMatcher(None, needle, words).ratio()
                if score > best_score:
                    best_score, best_index = score, index

            if best_index is None or best_score < 0.4:
                logger.info(
                    "Could not locate hook in transcript (best %.2f): %s",
                    best_score,
                    (moment.hook or "")[:60],
                )
                continue

            start, end = self._span(segments, best_index, moment)
            if video_duration:
                end = min(end, float(video_duration))
            if end - start < 12:
                continue

            score = int(moment.score) * (10 if rescale else 1)
            anchored.append(
                {
                    "start": start,
                    "end": end,
                    "title": moment.title,
                    "hook": moment.hook,
                    "reason": moment.reason,
                    "score": max(0, min(100, score)),
                }
            )

        return self._resolve_overlaps(anchored)

    @staticmethod
    def _uses_small_scale(moments) -> bool:
        """
        True when the model answered on a 1-10 scale despite the schema.

        Small models do this routinely. If nothing exceeds 10, read the whole
        set that way rather than presenting every clip as a single digit.
        """
        scores = [int(m.score) for m in moments] or [0]
        return max(scores) <= 10

    @staticmethod
    def _resolve_overlaps(moments: List[Dict]) -> List[Dict]:
        """Best score wins where two moments cover the same stretch."""
        moments.sort(key=lambda m: m["score"], reverse=True)
        kept: List[Dict] = []
        for candidate in moments:
            if not any(
                candidate["start"] < k["end"] and candidate["end"] > k["start"]
                for k in kept
            ):
                kept.append(candidate)
        return kept

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

        # Trust the model on which line is the hook, not on when it happens
        # or how long it lasts. Without a transcript to anchor against there
        # is nothing better than its own numbers, so they get cleaned instead.
        if segments:
            cleaned = self._anchor(moments, segments, video_duration)
        else:
            cleaned = self._sanitize(moments, video_duration)

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
        Clean the model's own timings, for when there is no transcript to
        anchor against. Mirrors MomentFinder._sanitize.
        """
        rescale = self._uses_small_scale(moments)
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
                # Overruns usually mean the model kept going past the payoff.
                # Trim to the cap rather than discarding a moment that started
                # in the right place.
                end = start + 60

            score = int(moment.score) * (10 if rescale else 1)
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

        return self._resolve_overlaps(cleaned)
