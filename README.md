# YouTube AI Clip Generator

A platform to automatically create viral clips from YouTube videos using AI analysis of audio, video, and content.

## Features

- 🎥 **Automatic Clip Detection** - AI analyzes video to find the most engaging moments
- 🎬 **Multi-Platform Publishing** - Publish clips to TikTok, Instagram Reels, and YouTube Shorts
- 📊 **Virality Scoring** - Advanced algorithm combining audio, video, and content analysis
- 🎤 **Audio Analysis** - Detects energy, onsets, tempo, and spectral changes
- 👁️ **Video Analysis** - Identifies scene cuts, motion, and brightness changes
- 📝 **Content Analysis** - Analyzes transcription, sentiment, and engagement keywords
- ⚡ **Async Processing** - Celery workers handle heavy lifting in the background
- 🔐 **User Authentication** - Secure JWT-based auth with social media OAuth tokens

## Tech Stack

### Backend
- **FastAPI** - Modern async web framework
- **PostgreSQL** - Relational database
- **Celery + Redis** - Asynchronous task queue
- **SQLAlchemy** - ORM for database operations
- **Librosa** - Audio analysis
- **OpenCV** - Video processing
- **Whisper** - Speech-to-text transcription
- **Transformers** - NLP for sentiment analysis

### Frontend
- **React 18** - UI library
- **TypeScript** - Type-safe JavaScript
- **TailwindCSS** - Utility-first CSS
- **Zustand** - State management
- **Axios** - HTTP client
- **Vite** - Build tool

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy and static file serving

## Project Structure

```
youtube-clip-generator/
├── backend/
│   ├── app/
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic validation schemas
│   │   ├── routes/        # FastAPI routes
│   │   ├── services/      # Business logic (YouTube, clip cutting, publishing)
│   │   ├── tasks/         # Celery async tasks
│   │   ├── main.py        # FastAPI app entry point
│   │   ├── config.py      # Configuration from env vars
│   │   ├── database.py    # SQLAlchemy setup
│   │   └── dependencies.py # Auth, JWT, etc.
│   ├── ai_engine/         # AI/ML modules
│   │   ├── virality_scorer.py     # Combines audio/video/content scores
│   │   ├── audio_analyzer.py      # Librosa-based audio analysis
│   │   ├── video_analyzer.py      # OpenCV-based video analysis
│   │   └── content_analyzer.py    # Whisper + NLP analysis
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components (Login, etc.)
│   │   ├── hooks/         # Custom React hooks
│   │   ├── services/      # API client
│   │   ├── store/         # Zustand state management
│   │   ├── types/         # TypeScript interfaces
│   │   ├── App.tsx        # Root component
│   │   ├── main.tsx       # Vite entry point
│   │   └── index.css      # Tailwind styles
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── Dockerfile
│   └── .env.example
│
├── docker-compose.yml     # Full stack orchestration
├── nginx.conf            # Nginx reverse proxy config
└── README.md

```

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Or: Python 3.11+, Node 18+, FFmpeg, PostgreSQL, Redis

### Running with Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd youtube-clip-generator
   ```

2. **Configure environment**
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```

3. **Update `.env` files with your credentials**
   - YouTube API key
   - TikTok API credentials
   - Instagram Graph API credentials
   - Database password (change default)

4. **Start the stack**
   ```bash
   docker-compose up -d
   ```

5. **Initialize the database**
   ```bash
   docker-compose exec backend python -m alembic upgrade head
   ```

6. **Access the app**
   - Frontend: http://localhost
   - Backend API: http://localhost:8000/api
   - API Docs: http://localhost:8000/docs

### Running Locally (Development)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://postgres:password@localhost:5432/clip_generator"
uvicorn app.main:app --reload
```

**Celery Worker:**
```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get access token
- `GET /api/auth/me` - Get current user info

### Videos
- `POST /api/videos/` - Add new YouTube video
- `GET /api/videos/` - List user's videos
- `GET /api/videos/{id}` - Get video details
- `DELETE /api/videos/{id}` - Delete video

### Clips
- `GET /api/clips/video/{video_id}` - Get clips for a video
- `GET /api/clips/{id}` - Get clip details
- `PUT /api/clips/{id}` - Update clip (title, caption, times)
- `DELETE /api/clips/{id}` - Delete clip

### Publishing
- `POST /api/publish/{clip_id}/tiktok` - Publish to TikTok
- `POST /api/publish/{clip_id}/instagram` - Publish to Instagram
- `POST /api/publish/{clip_id}/youtube` - Publish to YouTube Shorts
- `GET /api/publish/{clip_id}/analytics` - Get clip analytics

## Virality Scoring Algorithm

The system uses a three-component scoring model:

### 1. Audio Analysis (35%)
- Energy levels (RMS)
- Onset detection (sudden changes)
- Tempo/rhythm variations
- Spectral changes (timbre)

### 2. Video Analysis (35%)
- Scene cuts (histogram distance)
- Motion magnitude (optical flow)
- Brightness changes

### 3. Content Analysis (30%)
- Sentiment intensity
- Viral keywords ("amazing", "wait", "plot twist", etc.)
- Speech rate changes

Final score combines these with weights, smooths with Gaussian filter, and detects peaks above a threshold. Clips are extracted around detected peaks.

## Deployment

### Production Checklist

1. **Environment Variables**
   - Change `SECRET_KEY` to a strong random value
   - Set all social media API credentials
   - Use production database (not SQLite)
   - Set `DEBUG=False`

2. **Database**
   - Run migrations: `alembic upgrade head`
   - Set up backups
   - Use proper PostgreSQL user with limited permissions

3. **Security**
   - Use HTTPS (Nginx SSL certificates)
   - Rate limit API endpoints
   - Validate file uploads strictly
   - Use environment-specific secrets

4. **Monitoring**
   - Set up application logging
   - Monitor Celery task queue
   - Track API response times
   - Monitor disk/storage usage

## Contributing

1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Commit changes: `git commit -m 'Add amazing feature'`
3. Push to branch: `git push origin feature/amazing-feature`
4. Open a Pull Request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please open a GitHub issue.
