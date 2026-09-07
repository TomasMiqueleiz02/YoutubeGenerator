import json
import logging
from typing import Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class SocialCaption(BaseModel):
    """Ready-to-post text for one clip."""

    title: str = Field(description="Hook-first caption, under 100 characters")
    hashtags: List[str] = Field(
        description="4 to 6 hashtags without the # symbol, lowercase"
    )


SYSTEM_PROMPT = """You write the caption that goes under a short vertical video \
on TikTok, Reels and Shorts.

The caption is not a summary. It is the second hook, after the video's own \
opening line. It has to make someone stop scrolling.

What works:
- Lead with the tension, the claim or the number. Never with context.
- Speak the way the creator speaks in the clip, in the clip's own language.
- One line. If it needs a comma splice to stay short, use one.
- A question works when the video answers it.

What does not work: describing what happens ("he talks about being fired"), \
generic hype ("you won't believe this"), emoji, more than one idea.

Write exactly one sentence. Not a statement plus a question. One.
A caption that needs a full stop in the middle is two captions.

Hashtags: mix one or two broad tags with three or four specific to the actual \
subject. No hashtag spam, no unrelated trending tags."""


class CaptionWriter:
    """
    Writes post captions and hashtags from what is said in the clip.

    Runs on the same local model as clip selection, so this costs nothing per
    clip and needs no metered API.
    """

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None):
        self.model = model or settings.LOCAL_LLM_MODEL
        self.host = (host or settings.LOCAL_LLM_HOST).rstrip("/")

    @property
    def available(self) -> bool:
        if not settings.LOCAL_LLM_ENABLED:
            return False
        try:
            requests.get("%s/api/tags" % self.host, timeout=3).raise_for_status()
            return True
        except Exception:
            return False

    def write(
        self,
        clip_text: str,
        video_title: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Return {"title": str, "hashtags": [str]}, or None on any failure.

        A caption is a nice-to-have: never let it break clip generation.
        """
        if not clip_text.strip():
            return None

        try:
            user_content = (
                "Source video: %s\n"
                "Spoken language: %s\n"
                "Write the caption in that same language.\n\n"
                "What is said in this clip:\n%s"
                % (video_title or "unknown", language or "unknown", clip_text[:4000])
            )

            content = ""
            # Constrained JSON gets truncated often enough that a single shot
            # failed roughly one clip in three. Retry rather than drop it.
            for attempt in range(3):
                response = requests.post(
                    "%s/api/chat" % self.host,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_content},
                        ],
                        "format": SocialCaption.model_json_schema(),
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_ctx": 4096,
                            # Without an explicit budget the response gets cut
                            # mid-string and the JSON never closes.
                            "num_predict": 300,
                        },
                    },
                    timeout=90,
                )
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
                try:
                    json.loads(content)
                    break
                except json.JSONDecodeError:
                    logger.info("Caption JSON truncated, retry %d", attempt + 1)
                    content = ""

            if not content:
                return None

            caption = SocialCaption.model_validate(json.loads(content))

            # Models sometimes include the # despite being told not to
            tags = []
            seen = set()
            for tag in caption.hashtags[:6]:
                cleaned = tag.strip().lstrip("#").replace(" ", "").lower()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    tags.append(cleaned)

            title = self._clean_title(caption.title, tags, seen)
            return {"title": title, "hashtags": tags}

        except Exception:
            logger.exception("Caption generation failed")
            return None

    @staticmethod
    def _clean_title(title: str, tags: List[str], seen: set) -> str:
        """
        Strip what the model was told to keep out of the caption line.

        A 7B model follows the shape of the schema but not every instruction:
        it drops hashtags and emoji into the title anyway. Removing them here
        is deterministic, and any hashtag it buried there is worth keeping in
        the tag list rather than discarding.
        """
        import re

        for match in re.findall(r"#(\w+)", title):
            lowered = match.lower()
            if lowered not in seen and len(tags) < 6:
                seen.add(lowered)
                tags.append(lowered)

        title = re.sub(r"#\w+", "", title)
        # Emoji and pictographs, which read as filler in a caption
        title = re.sub(
            "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF]",
            "",
            title,
        )
        return re.sub(r"\s{2,}", " ", title).strip()[:150]


    @staticmethod
    def _clean_title(title: str, tags: List[str], seen: set) -> str:
        """
        Strip what the model was told to keep out of the caption line.

        A 7B model follows the shape of the schema but not every instruction:
        it drops hashtags and emoji into the title anyway. Removing them here
        is deterministic, and any hashtag it buried there is worth keeping in
        the tag list rather than discarding.
        """
        import re

        for match in re.findall(r"#(\w+)", title):
            lowered = match.lower()
            if lowered not in seen and len(tags) < 6:
                seen.add(lowered)
                tags.append(lowered)

        title = re.sub(r"#\w+", "", title)
        # Emoji and pictographs, which read as filler in a caption
        title = re.sub(
            "[🌀-🫿☀-➿🤀-🧿]",
            "",
            title,
        )
        return re.sub(r"\s{2,}", " ", title).strip()[:150]

    @staticmethod
    def format_for_post(caption: Dict) -> str:
        """Combine into the single string these platforms actually accept."""
        tags = " ".join("#%s" % t for t in caption.get("hashtags", []))
        return ("%s\n\n%s" % (caption.get("title", ""), tags)).strip()
