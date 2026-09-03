#!/bin/bash

echo "================================================"
echo "YouTube AI Clip Generator - Setup Script"
echo "================================================"
echo ""

# Check if .env files exist
if [ ! -f backend/.env ]; then
    echo "Creating backend/.env from template..."
    cp backend/.env.example backend/.env
    echo "  -> Created backend/.env (edit with your credentials)"
fi

if [ ! -f frontend/.env ]; then
    echo "Creating frontend/.env from template..."
    cp frontend/.env.example frontend/.env
    echo "  -> Created frontend/.env"
fi

echo ""
echo "================================================"
echo "Next steps:"
echo "================================================"
echo ""
echo "1. Edit backend/.env with your credentials:"
echo "   - YOUTUBE_API_KEY"
echo "   - TIKTOK_CLIENT_KEY & SECRET"
echo "   - INSTAGRAM_APP_ID & SECRET"
echo ""
echo "2. For local development:"
echo "   docker-compose up -d"
echo ""
echo "3. For Railway deployment:"
echo "   - Push to GitHub"
echo "   - Connect to railway.app"
echo "   - Add env vars in Railway dashboard"
echo "   - Railway will deploy automatically"
echo ""
echo "4. For development without Docker:"
echo "   Backend: cd backend && pip install -r requirements.txt && uvicorn app.main:app"
echo "   Frontend: cd frontend && npm install && npm run dev"
echo "   Celery: cd backend && celery -A app.tasks.celery_app worker"
echo ""
echo "================================================"
echo "Documentation:"
echo "================================================"
echo "- Local setup: see README.md"
echo "- Railway deployment: see DEPLOYMENT.md"
echo "- Quick start: see QUICK_START.md"
echo ""
