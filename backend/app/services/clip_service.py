import os
import subprocess
from typing import List, Optional

from app.config import settings


class ClipService:
    """Cuts clips out of a source video with FFmpeg and builds thumbnails."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(
            settings.LOCAL_STORAGE_PATH, "clips"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def cut_clip(
        self,
        source_path: str,
        clip_id: str,
        start_time: float,
        end_time: float,
        vertical: bool = True,
    ) -> str:
        """
        Extract [start_time, end_time] from the source video.

        When vertical is True the clip is re-framed to 1080x1920 (9:16) by
        cropping to a centre column, which is the format TikTok, Reels and
        Shorts expect.
        """
        if end_time <= start_time:
            raise ValueError("end_time must be greater than start_time")
        if not os.path.exists(source_path):
            raise FileNotFoundError("Source video not found: %s" % source_path)

        output_path = os.path.join(self.output_dir, "%s.mp4" % clip_id)
        duration = end_time - start_time

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", source_path,
            "-t", str(duration),
        ]

        if vertical:
            cmd += ["-vf", "crop=ih*9/16:ih,scale=1080:1920"]

        cmd += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]

        self._run(cmd)
        return output_path

    def generate_thumbnail(
        self, clip_path: str, clip_id: str, at_second: float = 1.0
    ) -> str:
        """Grab a single frame from a clip to use as its thumbnail."""
        thumbnail_path = os.path.join(self.output_dir, "%s.jpg" % clip_id)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(at_second),
            "-i", clip_path,
            "-vframes", "1",
            "-q:v", "3",
            thumbnail_path,
        ]
        self._run(cmd)
        return thumbnail_path

    def burn_subtitles(self, clip_path: str, srt_path: str, output_path: str) -> str:
        """Burn an SRT subtitle track into the clip."""
        quote = chr(39)
        escaped = srt_path.replace(chr(92), "/").replace(":", chr(92) + ":")
        subtitle_filter = "subtitles=" + quote + escaped + quote
        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-vf", subtitle_filter,
            "-c:a", "copy",
            output_path,
        ]
        self._run(cmd)
        return output_path

    def probe_duration(self, path: str) -> float:
        """Return the duration of a media file in seconds."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("ffprobe failed for %s" % path)
        return float(result.stdout.strip())

    def _run(self, cmd: List[str]) -> None:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            tail = (result.stderr or "").strip().splitlines()[-5:]
            raise RuntimeError("ffmpeg failed: %s" % " | ".join(tail))
