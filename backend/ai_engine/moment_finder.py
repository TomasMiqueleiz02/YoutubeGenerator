import logging
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class Moment(BaseModel):
    """One candidate clip chosen by the model."""

    start_seconds: float = Field(description="Clip start, in seconds from video start")
    end_seconds: float = Field(description="Clip end, in seconds from video start")
    title: str = Field(description="Short punchy title, under 60 characters")
    hook: str = Field(description="The opening line that grabs attention")
    reason: str = Field(description="Why this moment works as a standalone clip")
    score: int = Field(description="Predicted engagement, 0-100")


class MomentSelection(BaseModel):
    moments: List[Moment]


SYSTEM_PROMPT = """You find the moments in a long video that work as standalone \
short-form clips for TikTok, Reels and Shorts.

You receive a transcript where every line is prefixed with its start timestamp.

What makes a clip work:
- It opens with a hook: a claim, a question, a surprise, a strong opinion.
- It is self-contained. A viewer with no context understands it.
- It resolves. A setup without its payoff is a bad clip.
- It carries one idea, not three.

What does not work: throat-clearing intros, sponsor reads, rambling with no point, \
a punchline whose setup falls outside the clip.

Choose only genuinely strong moments. Four excellent clips beat twelve mediocre ones, \
and returning none is a valid answer for a video that has none.

Timing rules:
- Clips run 15 to 60 seconds.
- Start slightly before the hook so it does not feel clipped off.
- End just after the payoff lands, not in the middle of a sentence.
- Clips must not overlap each other.
- Never place a timestamp beyond the end of the video."""


class MomentFinder:
    """Picks clip-worthy moments by reading the transcript, not by measuring energy."""

    def __init__(self, model: str = "claude-opus-5"):
        self.model = model

    @property
    def available(self) -> bool:
        return bool(settings.ANTHROPIC_API_KEY)

    def find(
        self,
        transcript_text: str,
        video_duration: float,
        video_title: Optional[str] = None,
        max_clips: int = 10,
    ) -> List[Dict]:
        """
        Return chosen moments, or an empty list when unavailable or unusable.

        Never raises: a failure here should fall back to signal-based detection
        rather than sink the whole job.
        """
        if not self.available:
            logger.info("No Anthropic API key configured; skipping semantic selection")
            return []

        if not transcript_text.strip():
            logger.info("Empty transcript; skipping semantic selection")
            return []

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

            user_content = (
                "Video title: %s\n"
                "Video duration: %d seconds\n"
                "Return at most %d clips.\n\n"
                "Transcript:\n%s"
                % (
                    video_title or "unknown",
                    int(video_duration),
                    max_clips,
                    transcript_text,
                )
            )

            response = client.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
                output_format=MomentSelection,
            )

            if response.stop_reason == "refusal":
                logger.warning("Model declined the request: %s", response.stop_details)
                return []

            selection = response.parsed_output
            if selection is None:
                return []

            return self._sanitize(selection.moments, video_duration)

        except Exception:
            logger.exception("Semantic moment selection failed; falling back")
            return []

    def _sanitize(self, moments: List[Moment], video_duration: float) -> List[Dict]:
        """Drop moments that break timing rules and resolve any overlaps."""
        cleaned: List[Dict] = []

        for moment in moments:
            start = max(0.0, float(moment.start_seconds))
            end = float(moment.end_seconds)

            if video_duration:
                end = min(end, float(video_duration))

            duration = end - start
            if duration < 10 or duration > 90:
                logger.info("Discarding moment of %.1fs (out of range)", duration)
                continue

            cleaned.append(
                {
                    "start": start,
                    "end": end,
                    "title": moment.title,
                    "hook": moment.hook,
                    "reason": moment.reason,
                    "score": max(0, min(100, int(moment.score))),
                }
            )

        # Highest scoring wins any overlap
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
