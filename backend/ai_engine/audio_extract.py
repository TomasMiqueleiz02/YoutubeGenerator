import logging
import os
import subprocess
import tempfile
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def extracted_audio(media_path: str, sample_rate: int = 22050):
    """
    Yield a temporary mono WAV path holding the media file's audio.

    librosa reads through soundfile, which handles WAV but not the MP4
    container, so audio has to come out with ffmpeg first. Decoding once to
    WAV is also faster than letting a decoder re-open the video per analysis.
    """
    handle, wav_path = tempfile.mkstemp(prefix="audio_", suffix=".wav")
    os.close(handle)

    cmd = [
        "ffmpeg", "-y",
        "-i", media_path,
        "-vn",                    # drop the video stream
        "-ac", "1",               # mono
        "-ar", str(sample_rate),
        "-f", "wav",
        wav_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            tail = (result.stderr or "").strip().splitlines()[-3:]
            raise RuntimeError("ffmpeg could not extract audio: %s" % " | ".join(tail))
        yield wav_path
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass
