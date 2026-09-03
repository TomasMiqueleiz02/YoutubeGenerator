import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp: H:MM:SS.cc (centiseconds)."""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return "%d:%02d:%05.2f" % (hours, minutes, secs)


def _escape(text: str) -> str:
    """Escape the characters ASS treats as markup."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


class SubtitleStyle:
    """
    Visual preset for burned-in captions.

    Defaults target a 1080x1920 vertical clip: large bold text, a heavy outline
    so it stays readable over any footage, and the active word highlighted the
    way short-form captions usually do it.
    """

    def __init__(
        self,
        font: str = "Arial Black",
        font_size: int = 78,
        primary_color: str = "&H00FFFFFF",     # white  (ASS is &HAABBGGRR)
        highlight_color: str = "&H0000E5FF",   # amber
        outline_color: str = "&H00000000",     # black
        outline_width: int = 6,
        shadow: int = 3,
        margin_vertical: int = 420,
        words_per_line: int = 3,
        uppercase: bool = True,
    ):
        self.font = font
        self.font_size = font_size
        self.primary_color = primary_color
        self.highlight_color = highlight_color
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.shadow = shadow
        self.margin_vertical = margin_vertical
        self.words_per_line = words_per_line
        self.uppercase = uppercase


class SubtitleGenerator:
    """
    Builds burned-in captions in ASS format.

    ASS rather than SRT because SRT carries no styling: no font size, no
    outline, no per-word highlight. Short-form captions need all three.
    """

    def __init__(self, style: Optional[SubtitleStyle] = None):
        self.style = style or SubtitleStyle()

    def build(
        self,
        segments: List[Dict],
        clip_start: float,
        clip_end: float,
        width: int = 1080,
        height: int = 1920,
    ) -> Optional[str]:
        """
        Return ASS subtitle text covering [clip_start, clip_end].

        Timestamps are rebased to the clip, since the cut file starts at zero.
        Returns None when the range holds no usable words.
        """
        groups = self._group_words(segments, clip_start, clip_end)
        if not groups:
            logger.info("No words in %.1f-%.1f; skipping captions", clip_start, clip_end)
            return None

        lines = [self._header(width, height), self._styles(), self._events(groups)]
        return "\n".join(lines)

    def _group_words(
        self, segments: List[Dict], clip_start: float, clip_end: float
    ) -> List[List[Dict]]:
        """Collect words inside the clip and chunk them into short lines."""
        words: List[Dict] = []

        for segment in segments:
            for word in segment.get("words") or []:
                start = float(word["start"])
                end = float(word["end"])
                # Keep any word that overlaps the clip window
                if end <= clip_start or start >= clip_end:
                    continue
                words.append(
                    {
                        "start": max(start, clip_start) - clip_start,
                        "end": min(end, clip_end) - clip_start,
                        "text": word["text"],
                    }
                )

        groups: List[List[Dict]] = []
        size = max(1, self.style.words_per_line)
        for i in range(0, len(words), size):
            chunk = words[i : i + size]
            if chunk:
                groups.append(chunk)
        return groups

    def _header(self, width: int, height: int) -> str:
        return (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "WrapStyle: 2\n"
            "ScaledBorderAndShadow: yes\n"
            "PlayResX: %d\n"
            "PlayResY: %d\n" % (width, height)
        )

    def _styles(self) -> str:
        s = self.style
        return (
            "\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Caption,%s,%d,%s,%s,%s,&H00000000,-1,0,0,0,"
            "100,100,0,0,1,%d,%d,2,60,60,%d,1\n"
            % (
                s.font,
                s.font_size,
                s.primary_color,
                s.highlight_color,
                s.outline_color,
                s.outline_width,
                s.shadow,
                s.margin_vertical,
            )
        )

    def _events(self, groups: List[List[Dict]]) -> str:
        header = (
            "\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
            "MarginV, Effect, Text\n"
        )
        rows = []

        for group in groups:
            start = group[0]["start"]
            end = group[-1]["end"]
            if end <= start:
                end = start + 0.3

            # One dialogue line per group; the active word is recolored as
            # playback reaches it, which is the familiar karaoke effect.
            for index, word in enumerate(group):
                w_start = word["start"]
                w_end = word["end"] if word["end"] > w_start else w_start + 0.2
                if index == len(group) - 1:
                    w_end = max(w_end, end)

                parts = []
                for j, other in enumerate(group):
                    token = other["text"]
                    if self.style.uppercase:
                        token = token.upper()
                    token = _escape(token)
                    if j == index:
                        parts.append(
                            "{\\c%s\\fscx112\\fscy112}%s{\\c%s\\fscx100\\fscy100}"
                            % (self.style.highlight_color, token, self.style.primary_color)
                        )
                    else:
                        parts.append(token)

                rows.append(
                    "Dialogue: 0,%s,%s,Caption,,0,0,0,,%s"
                    % (_ass_time(w_start), _ass_time(w_end), " ".join(parts))
                )

        return header + "\n".join(rows) + "\n"
