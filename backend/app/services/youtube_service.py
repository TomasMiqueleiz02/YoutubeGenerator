import os
import re
import tempfile
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

import yt_dlp

from app.config import settings


class YouTubeService:
    """Downloads videos and reads metadata from YouTube via yt-dlp."""

    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = download_dir or os.path.join(
            settings.LOCAL_STORAGE_PATH, "videos"
        )
        os.makedirs(self.download_dir, exist_ok=True)
        self._cookies_path = self._write_cookies_file()

    def _write_cookies_file(self) -> Optional[str]:
        """
        Persist YTDLP_COOKIES_CONTENT to a temp file, if configured.

        YouTube blocks download requests from datacenter IPs (Railway
        included) with "Sign in to confirm you're not a bot" unless the
        request carries cookies from a real logged-in session.
        """
        content = settings.YTDLP_COOKIES_CONTENT
        if not content:
            return None
        fd, path = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def _base_opts(self) -> Dict:
        opts: Dict = {"quiet": True, "no_warnings": True}
        if self._cookies_path:
            opts["cookiefile"] = self._cookies_path
        return opts

    def _strategies(self) -> List[Dict]:
        """
        Extraction strategies tried in order until one yields formats.

        YouTube blocks its own player clients in different ways over time and
        by requesting IP, so no single client stays reliable. Some clients also
        reject cookies, so cookie-less variants are included as fallbacks.
        """
        clients = [
            "default",
            "web_safari",
            "mweb",
            "tv",
            "ios",
            "android",
        ]

        strategies: List[Dict] = []
        for client in clients:
            # With cookies (authenticated session)
            if self._cookies_path:
                opts = self._base_opts()
                if client != "default":
                    opts["extractor_args"] = {"youtube": {"player_client": [client]}}
                strategies.append(opts)
            # Without cookies: some clients refuse authenticated requests
            plain: Dict = {"quiet": True, "no_warnings": True}
            if client != "default":
                plain["extractor_args"] = {"youtube": {"player_client": [client]}}
            strategies.append(plain)
        return strategies

    def _extract(self, url: str, extra_opts: Dict, download: bool):
        """
        Run extract_info against each strategy, returning the first success.

        Raises the last error if every strategy fails, so the caller still
        sees a real YouTube message rather than a generic failure.
        """
        last_error: Optional[Exception] = None

        for strategy in self._strategies():
            opts = {**strategy, **extra_opts}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=download)
                if info:
                    return info, ydl
            except Exception as exc:  # noqa: BLE001 - try the next strategy
                last_error = exc
                continue

        raise last_error or RuntimeError("yt-dlp could not extract %s" % url)

    def extract_video_id(self, url: str) -> str:
        """Extract the 11-character YouTube video id from any common URL form."""
        parsed = urlparse(url)

        if parsed.hostname in ("youtu.be",):
            candidate = parsed.path.lstrip("/")
            if candidate:
                return candidate.split("/")[0]

        if parsed.hostname and "youtube" in parsed.hostname:
            if parsed.path == "/watch":
                query = parse_qs(parsed.query)
                if "v" in query:
                    return query["v"][0]
            match = re.match(r"^/(embed|shorts|v)/([^/?#]+)", parsed.path)
            if match:
                return match.group(2)

        # Fall back to a bare id
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
            return url

        raise ValueError("Could not extract a YouTube video id from: %s" % url)

    def get_video_metadata(self, video_id: str) -> Dict:
        """Fetch title, channel, duration and thumbnail without downloading."""
        url = "https://www.youtube.com/watch?v=%s" % video_id
        info, _ = self._extract(url, {"skip_download": True}, download=False)

        return {
            "title": info.get("title") or "Untitled",
            "channel": info.get("uploader") or info.get("channel") or "Unknown",
            "thumbnail": info.get("thumbnail"),
            "duration": int(info.get("duration") or 0),
            "width": info.get("width"),
            "height": info.get("height"),
            "fps": info.get("fps"),
        }

    def download_video(self, youtube_url: str, video_id: Optional[str] = None) -> str:
        """
        Download a video to local storage and return its file path.
        Caps resolution at 1080p to keep processing time reasonable.
        """
        video_id = video_id or self.extract_video_id(str(youtube_url))
        output_template = os.path.join(self.download_dir, "%s.%%(ext)s" % video_id)

        extra_opts = {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "merge_output_format": "mp4",
            "outtmpl": output_template,
            "noprogress": True,
        }

        info, ydl = self._extract(str(youtube_url), extra_opts, download=True)
        file_path = ydl.prepare_filename(info)

        # yt-dlp reports the pre-merge extension, so prefer the merged mp4
        merged = os.path.splitext(file_path)[0] + ".mp4"
        if os.path.exists(merged):
            return merged
        if os.path.exists(file_path):
            return file_path

        raise FileNotFoundError("Download finished but no output file was found")
