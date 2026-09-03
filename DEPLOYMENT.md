# Deployment a Railway

Railway soporta full-stack deployment. Aquí están los pasos para desplegar tu app.

## Requisitos Previos

1. Cuenta en [railway.app](https://railway.app) (conecta con GitHub)
2. Tu proyecto en GitHub (public o private)
3. Credenciales de APIs (YouTube, TikTok, Instagram)

## Pasos de Deployment

### 1. Preparar el repositorio

```bash
cd youtube-clip-generator
git init
git add .
git commit -m "Initial commit: YouTube Clip Generator"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/youtube-clip-generator.git
git push -u origin main
```

### 2. Crear proyecto en Railway

1. Ve a [railway.app](https://railway.app)
2. Click **"New Project"**
3. Selecciona **"Deploy from GitHub"**
4. Conecta tu cuenta GitHub (autoriza Railway)
5. Selecciona el repo `youtube-clip-generator`
6. Railway detectará automáticamente docker-compose.yml

### 3. Configurar variables de entorno

En el dashboard de Railway, para cada servicio, añade las variables:

**Backend (FastAPI):**
```
DATABASE_URL=postgresql://[USER]:[PASS]@[HOST]:5432/clip_generator
CELERY_BROKER_URL=redis://[USER]:[PASS]@[HOST]:6379/0
CELERY_RESULT_BACKEND=redis://[USER]:[PASS]@[HOST]:6379/1
SECRET_KEY=<generate-strong-random-string>
CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
TIKTOK_CLIENT_KEY=<your-tiktok-key>
TIKTOK_CLIENT_SECRET=<your-tiktok-secret>
INSTAGRAM_APP_ID=<your-instagram-app-id>
INSTAGRAM_APP_SECRET=<your-instagram-secret>
YOUTUBE_API_KEY=<your-youtube-api-key>
```

**PostgreSQL (Railway lo crea automáticamente):**
- Railway genera credenciales automáticamente

**Redis (Railway lo crea automáticamente):**
- Railway genera URL automáticamente

**Frontend:**
```
VITE_API_URL=https://your-backend-domain.railway.app/api
```

### 4. Desplegar

```bash
git push origin main
```

Railway automáticamente:
1. Detecta cambios en el repo
2. Build de contenedores
3. Deploy de todos los servicios
4. Las URLs se generan automáticamente

### 5. URLs después del deploy

Railway te dará:
- **Backend**: `https://your-backend-xxx.railway.app`
- **Frontend**: `https://your-frontend-xxx.railway.app`
- **API Docs**: `https://your-backend-xxx.railway.app/docs`

### 6. Verificar que funciona

```bash
# Health check del backend
curl https://your-backend-xxx.railway.app/health

# Acceder al frontend
https://your-frontend-xxx.railway.app
```

## Archivos importantes para Railway

- `docker-compose.yml` - Railway lee esto automáticamente
- `backend/Dockerfile` - Build del backend
- `frontend/Dockerfile` - Build del frontend
- `.env` files se ignoran, todo en Railway dashboard

## Troubleshooting

### Backend no inicia
- Verifica que `DATABASE_URL` esté correcta
- Check logs en Railway dashboard (Logs tab)
- Asegúrate de que PostgreSQL está ✅

### Frontend no conecta al backend
- Verifica `VITE_API_URL` en frontend
- Debe ser la URL completa del backend Railway
- No debe tener trailing slash

### Celery no procesa tasks
- Verifica que Redis está corriendo
- Que las variables de `CELERY_BROKER_URL` son correctas
- Revisa logs del Celery worker en Railway

## Escalado (después de deploy inicial)

### Agregar más workers de Celery
En `docker-compose.yml`:
```yaml
celery_worker_2:
  build: ./backend
  command: celery -A app.tasks.celery_app worker --loglevel=info
  # ... rest del config
```

### Aumentar replicas del backend
En Railway dashboard:
- Servicio → Settings → Replicas (aumentar número)

## Costos aproximados

- PostgreSQL: ~$12/mes (Railway proporciona créditos gratis iniciales)
- Redis: ~$7/mes
- Backend compute: ~$5-10/mes
- Frontend: ~$5/mes (o gratis si es estático)

**Total: ~$30-40/mes** (con créditos iniciales Railway: ~3 meses gratis)

## Siguientes pasos

1. Setup OAuth en TikTok, Instagram, YouTube
2. Configurar backups de BD
3. Setup de logging/monitoring
4. Custom domain (settings en Railway)

¿Necesitas ayuda con algún paso específico?
