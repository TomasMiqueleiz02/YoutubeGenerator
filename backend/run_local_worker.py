"""
Start the processing worker on this machine.

Why this exists: YouTube blocks downloads from datacenter IPs, so the cloud
worker cannot fetch videos. A home connection is not blocked, so the worker
runs here and talks to the Railway database, queue and storage over the
network.

Usage:  python run_local_worker.py
Stop:   Ctrl+C  (queued videos stay queued and resume next run)
"""

import os
import shutil
import sys
from pathlib import Path


def ensure_ffmpeg() -> None:
    """
    Make sure ffmpeg is callable, adding it to PATH if needed.

    A fresh winget install writes ffmpeg to PATH, but only for shells started
    afterwards. Rather than making the user reboot a terminal, find the
    executable and put its directory on this process's PATH.
    """
    if shutil.which("ffmpeg"):
        return

    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Microsoft" / "WinGet" / "Packages")
    for root in candidates:
        if not root.exists():
            continue
        for exe in root.rglob("ffmpeg.exe"):
            os.environ["PATH"] = str(exe.parent) + os.pathsep + os.environ.get("PATH", "")
            print("Found ffmpeg at %s" % exe)
            return

    print(
        "WARNING: ffmpeg not found. Clip cutting and audio analysis will fail.\n"
        "         Install it with:  winget install Gyan.FFmpeg"
    )


def load_env(path: Path) -> int:
    if not path.exists():
        sys.exit(
            "Missing %s\nThis file holds the database credentials." % path
        )

    loaded = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()
        loaded += 1
    return loaded


def main() -> None:
    here = Path(__file__).resolve().parent
    os.chdir(here)
    sys.path.insert(0, str(here))

    # Celery imports task modules in a fresh context, so a sys.path tweak
    # alone does not survive. PYTHONPATH does.
    existing = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = (
        str(here) + (os.pathsep + existing if existing else "")
    )

    ensure_ffmpeg()

    count = load_env(here / ".env.local")
    print("Loaded %d settings from .env.local" % count)
    print("Starting worker. Leave this window open while videos process.\n")

    from app.tasks.celery_app import celery_app

    # solo pool: Windows lacks fork(), which the default prefork pool needs
    celery_app.worker_main(
        ["worker", "--loglevel=info", "--pool=solo", "--without-gossip", "--without-mingle"]
    )


if __name__ == "__main__":
    main()
