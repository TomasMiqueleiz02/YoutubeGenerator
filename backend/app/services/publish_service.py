import os
import time
from typing import Dict, Optional

import requests

TIKTOK_API = "https://open.tiktokapis.com/v2"
GRAPH_API = "https://graph.facebook.com/v18.0"
YOUTUBE_UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3/videos"


class PublishService:
    """
    Publishes clips to TikTok, Instagram Reels and YouTube Shorts.

    Each platform needs an OAuth access token obtained through its own consent
    flow and stored on the user record.
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    # ---------------- TikTok ----------------

    def publish_to_tiktok(
        self,
        clip_file_path: str,
        title: Optional[str],
        caption: Optional[str],
        access_token: str,
    ) -> Dict:
        """
        Direct Post flow: initialize an upload, PUT the file, return the publish id.

        Note that unaudited TikTok apps can only post with SELF_ONLY privacy.
        """
        if not clip_file_path or not os.path.exists(clip_file_path):
            raise FileNotFoundError("Clip file not found: %s" % clip_file_path)

        file_size = os.path.getsize(clip_file_path)
        headers = {
            "Authorization": "Bearer %s" % access_token,
            "Content-Type": "application/json",
        }
        payload = {
            "post_info": {
                "title": (title or caption or "")[:150],
                "privacy_level": "SELF_ONLY",
                "disable_comment": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }

        init = requests.post(
            "%s/post/publish/video/init/" % TIKTOK_API,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        init.raise_for_status()
        data = init.json().get("data", {})

        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")
        if not upload_url or not publish_id:
            raise RuntimeError("TikTok did not return an upload URL")

        with open(clip_file_path, "rb") as handle:
            upload = requests.put(
                upload_url,
                data=handle,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": "bytes 0-%d/%d" % (file_size - 1, file_size),
                },
                timeout=self.timeout * 5,
            )
        upload.raise_for_status()

        return {"post_id": publish_id, "platform": "tiktok"}

    # ---------------- Instagram ----------------

    def publish_to_instagram(
        self,
        clip_file_path: str,
        caption: Optional[str],
        access_token: str,
        ig_user_id: Optional[str] = None,
        public_video_url: Optional[str] = None,
    ) -> Dict:
        """
        Reels flow: create a media container from a publicly reachable URL, wait
        for Instagram to finish processing, then publish it.

        Instagram pulls the file itself, so the clip must already be hosted at a
        public URL (S3, a CDN, or the static host of this app).
        """
        if not public_video_url:
            raise ValueError(
                "Instagram requires a public video URL. Upload the clip to S3 "
                "or another public host before publishing."
            )
        if not ig_user_id:
            ig_user_id = self._get_instagram_user_id(access_token)

        container = requests.post(
            "%s/%s/media" % (GRAPH_API, ig_user_id),
            data={
                "media_type": "REELS",
                "video_url": public_video_url,
                "caption": caption or "",
                "access_token": access_token,
            },
            timeout=self.timeout,
        )
        container.raise_for_status()
        creation_id = container.json().get("id")

        self._wait_for_instagram_container(creation_id, access_token)

        published = requests.post(
            "%s/%s/media_publish" % (GRAPH_API, ig_user_id),
            data={"creation_id": creation_id, "access_token": access_token},
            timeout=self.timeout,
        )
        published.raise_for_status()

        return {"post_id": published.json().get("id"), "platform": "instagram"}

    def _get_instagram_user_id(self, access_token: str) -> str:
        response = requests.get(
            "%s/me/accounts" % GRAPH_API,
            params={"access_token": access_token},
            timeout=self.timeout,
        )
        response.raise_for_status()
        accounts = response.json().get("data", [])
        if not accounts:
            raise RuntimeError("No Instagram business account linked to this token")
        return accounts[0]["id"]

    def _wait_for_instagram_container(
        self, creation_id: str, access_token: str, max_attempts: int = 30
    ) -> None:
        """Poll the container until Instagram finishes transcoding."""
        for _ in range(max_attempts):
            status = requests.get(
                "%s/%s" % (GRAPH_API, creation_id),
                params={"fields": "status_code", "access_token": access_token},
                timeout=self.timeout,
            )
            status.raise_for_status()
            code = status.json().get("status_code")
            if code == "FINISHED":
                return
            if code == "ERROR":
                raise RuntimeError("Instagram failed to process the video")
            time.sleep(5)
        raise TimeoutError("Instagram container did not finish processing in time")

    # ---------------- YouTube Shorts ----------------

    def publish_to_youtube_shorts(
        self,
        clip_file_path: str,
        title: Optional[str],
        caption: Optional[str],
        access_token: str,
    ) -> Dict:
        """Resumable upload to YouTube. Clips under 60s are treated as Shorts."""
        if not clip_file_path or not os.path.exists(clip_file_path):
            raise FileNotFoundError("Clip file not found: %s" % clip_file_path)

        file_size = os.path.getsize(clip_file_path)
        metadata = {
            "snippet": {
                "title": (title or "Clip")[:100],
                "description": caption or "",
                "categoryId": "22",
            },
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
        }

        session = requests.post(
            YOUTUBE_UPLOAD_API,
            params={"uploadType": "resumable", "part": "snippet,status"},
            json=metadata,
            headers={
                "Authorization": "Bearer %s" % access_token,
                "X-Upload-Content-Length": str(file_size),
                "X-Upload-Content-Type": "video/mp4",
            },
            timeout=self.timeout,
        )
        session.raise_for_status()
        upload_url = session.headers.get("Location")
        if not upload_url:
            raise RuntimeError("YouTube did not return a resumable upload URL")

        with open(clip_file_path, "rb") as handle:
            upload = requests.put(
                upload_url,
                data=handle,
                headers={"Content-Type": "video/mp4"},
                timeout=self.timeout * 10,
            )
        upload.raise_for_status()

        return {"post_id": upload.json().get("id"), "platform": "youtube_shorts"}

    # ---------------- Analytics ----------------

    def fetch_tiktok_analytics(self, post_id: str, access_token: str) -> Dict:
        response = requests.post(
            "%s/video/query/" % TIKTOK_API,
            params={"fields": "id,like_count,comment_count,share_count,view_count"},
            json={"filters": {"video_ids": [post_id]}},
            headers={"Authorization": "Bearer %s" % access_token},
            timeout=self.timeout,
        )
        response.raise_for_status()
        videos = response.json().get("data", {}).get("videos", [])
        return videos[0] if videos else {}

    def fetch_instagram_analytics(self, post_id: str, access_token: str) -> Dict:
        response = requests.get(
            "%s/%s/insights" % (GRAPH_API, post_id),
            params={
                "metric": "plays,likes,comments,shares,saved",
                "access_token": access_token,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return {
            item["name"]: item["values"][0]["value"]
            for item in response.json().get("data", [])
        }
