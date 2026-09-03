import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.database import engine
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

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(clips.router, prefix="/api/clips", tags=["Clips"])
app.include_router(publish.router, prefix="/api/publish", tags=["Publish"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "youtube-clip-generator"}


@app.get("/")
async def root():
    return {"message": "Welcome to YouTube AI Clip Generator API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
