import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Phrases that typically open a hook: the speaker is about to reveal,
# claim, or contradict something. Spanish and English, since transcripts
# come in whatever the video was recorded in.
HOOK_MARKERS = [
    # English
    "the problem is", "what nobody tells you", "here's the thing",
    "the truth is", "i realized", "it turns out", "the secret",
    "most people", "let me tell you", "the reason", "the key is",
    "i was wrong", "nobody talks about", "the mistake",
    "what happened was", "the crazy part", "and then",
    # Spanish
    "el problema es", "lo que nadie", "la verdad es", "me di cuenta",
    "resulta que", "el secreto", "la mayoria", "la mayoría",
    "te voy a contar", "la razon", "la razón", "la clave",
    "estaba equivocado", "nadie habla", "el error",
    "lo que paso", "lo que pasó", "lo loco es", "y ahi", "y ahí",
]

# Words signalling intensity or stakes
INTENSITY_MARKERS = [
    # English
    "never", "always", "worst", "best", "insane", "crazy", "incredible",
    "shocking", "huge", "massive", "terrible", "amazing", "impossible",
    "everyone", "nobody", "actually", "literally", "completely",
    # Spanish
    "nunca", "siempre", "peor", "mejor", "increible", "increíble",
    "loco", "tremendo", "enorme", "terrible", "imposible", "todos",
    "nadie", "realmente", "literalmente", "completamente", "jamas", "jamás",
]

# Openers that mark filler rather than substance
FILLER_MARKERS = [
    "subscribe", "like and", "smash that", "sponsored by", "our sponsor",
    "link in the description", "before we start", "welcome back",
    "suscribite", "suscríbete", "dale like", "patrocinado",
    "link en la descripcion", "link en la descripción",
    "antes de empezar", "bienvenidos de nuevo",
]


class HeuristicMomentFinder:
    """
    Picks clip-worthy moments by reading the transcript with text heuristics.

    Free and local: no API, no model weights beyond the transcript itself.
    Weaker than a language model at judging whether an idea actually lands,
    but it reads what is being said instead of how loud it is.
    """

    def __init__(
        self,
        min_duration: float = 18.0,
        max_duration: float = 60.0,
        target_duration: float = 35.0,
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.target_duration = target_duration

    def find(
        self,
        transcript: Dict,
        video_duration: float,
        max_clips: int = 8,
    ) -> List[Dict]:
        segments = transcript.get("segments", [])
        if not segments:
            return []

        scored = [self._score_segment(s) for s in segments]
        windows = self._build_windows(segments, scored, video_duration)

        windows.sort(key=lambda w: w["score"], reverse=True)
        kept: List[Dict] = []
        for window in windows:
            overlaps = any(
                window["start"] < k["end"] and window["end"] > k["start"]
                for k in kept
            )
            if not overlaps:
                kept.append(window)
            if len(kept) >= max_clips:
                break

        logger.info("Heuristic selection produced %d moments", len(kept))
        return kept

    def _score_segment(self, segment: Dict) -> float:
        """Score a single transcript segment on how clip-worthy its text is."""
        text = (segment.get("text") or "").lower()
        if not text:
            return 0.0

        score = 40.0

        # A question is a natural hook
        if "?" in text:
            score += 18

        # Hook phrasing is the strongest single signal
        for marker in HOOK_MARKERS:
            if marker in text:
                score += 22
                break

        # Intensity words, capped so a rant does not dominate
        intensity_hits = sum(1 for m in INTENSITY_MARKERS if m in text)
        score += min(intensity_hits * 7, 21)

        # Concrete numbers usually mean substance, not filler
        if re.search(r"\b\d[\d.,]*\s*(%|percent|por ciento|mil|million|millones)?\b", text):
            score += 8

        # Filler is actively penalized
        for marker in FILLER_MARKERS:
            if marker in text:
                score -= 35
                break

        # Very short fragments rarely carry an idea
        word_count = len(text.split())
        if word_count < 4:
            score -= 15
        elif word_count > 12:
            score += 6

        return max(0.0, min(100.0, score))

    def _build_windows(
        self,
        segments: List[Dict],
        scored: List[float],
        video_duration: float,
    ) -> List[Dict]:
        """
        Grow a candidate window from each promising segment.

        Each window starts on a strong segment (the hook) and extends forward
        until it reaches a natural length, so the clip contains its own payoff
        rather than cutting off at the hook.
        """
        windows: List[Dict] = []

        for index, segment in enumerate(segments):
            if scored[index] < 55:
                continue  # not a strong enough opener

            start = float(segment["start"])
            end = start
            total = 0.0
            weighted = 0.0
            cursor = index

            while cursor < len(segments):
                candidate_end = float(segments[cursor]["end"])
                if candidate_end - start > self.max_duration:
                    break
                end = candidate_end
                weighted += scored[cursor]
                total += 1
                cursor += 1
                if end - start >= self.target_duration:
                    break

            duration = end - start
            if duration < self.min_duration:
                # Extend to the minimum if there is video left to use
                end = min(start + self.min_duration, video_duration or end)
                duration = end - start
                if duration < self.min_duration:
                    continue

            mean_score = weighted / total if total else 0.0
            # Reward the opener heavily: the first seconds decide whether
            # a short-form viewer keeps watching.
            final_score = 0.6 * scored[index] + 0.4 * mean_score

            text = " ".join(
                (segments[i].get("text") or "")
                for i in range(index, min(cursor, len(segments)))
            ).strip()

            windows.append(
                {
                    "start": start,
                    "end": end,
                    "score": round(final_score, 1),
                    "title": self._make_title(text),
                    "hook": (segments[index].get("text") or "").strip()[:200],
                    "reason": "Opens on a strong line and runs to a natural stop",
                }
            )

        return windows

    @staticmethod
    def _make_title(text: str) -> Optional[str]:
        """Use the opening words as a working title."""
        if not text:
            return None
        clean = re.sub(r"\s+", " ", text).strip()
        words = clean.split()
        title = " ".join(words[:9])
        if len(words) > 9:
            title += "..."
        return title[:80]
