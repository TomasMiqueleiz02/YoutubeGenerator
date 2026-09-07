import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.database import engine
from app.models import Base
from app.routes import auth, clips, publish, videos

app = FastAPI(
    title="YouTube AI Clip Generator",
    description="Automatically create viral clips from YouTube videos",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.on_event("startup")
def create_tables():
    """Create tables on startup. Runs after the DB is reachable, unlike a
    module-level call which would crash the process on transient DB errors."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        logger.exception("Could not create database tables on startup")


app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(clips.router, prefix="/api/clips", tags=["Clips"])
app.include_router(publish.router, prefix="/api/publish", tags=["Publish"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "youtube-clip-generator"}


@app.get("/api/worker/status")
async def worker_status():
    """
    Report whether the machine that processes videos is running.

    Downloads happen on a PC at home rather than here, because YouTube blocks
    datacenter addresses. That machine can be switched off, and when it is,
    an upload sits at "pending" with nothing to explain why. The worker
    writes an expiring key while it lives; this reads it, so the page can
    say so instead of leaving someone waiting on a queue nobody is serving.
    """
    import json

    import redis

    from app.tasks.heartbeat import HEARTBEAT_KEY

    try:
        client = redis.from_url(settings.CELERY_BROKER_URL)
        raw = client.get(HEARTBEAT_KEY)
    except Exception:
        logger.exception("Could not read the worker heartbeat")
        # The broker being unreachable from here says nothing about the
        # worker, so do not claim it is down.
        return {"online": None, "hostname": None, "last_seen": None}

    if not raw:
        return {"online": False, "hostname": None, "last_seen": None}

    try:
        beat = json.loads(raw)
    except ValueError:
        return {"online": True, "hostname": None, "last_seen": None}

    return {
        "online": True,
        "hostname": beat.get("hostname"),
        "last_seen": beat.get("at"),
    }


@app.get("/")
async def root():
    return {"message": "Welcome to YouTube AI Clip Generator API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
