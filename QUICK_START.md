# Railway Deployment - Quick Start

## En 5 minutos:

### 1. Push a GitHub
```bash
git init
git add .
git commit -m "YouTube Clip Generator"
git remote add origin https://github.com/TU_USUARIO/youtube-clip-generator.git
git branch -M main
git push -u origin main
```

### 2. Railway Dashboard
1. Ve a [railway.app](https://railway.app)
2. Click **"New Project"** → **"Deploy from GitHub"**
3. Selecciona tu repo
4. Railway lee `docker-compose.yml` automáticamente ✅

### 3. Environment Variables (en Railway Dashboard)

**Backend service:**
```
DATABASE_URL=postgresql://...  # Railway genera esto
CELERY_BROKER_URL=redis://...   # Railway genera esto
SECRET_KEY=tu-clave-secreta-fuerte
CORS_ORIGINS=["https://tu-frontend.railway.app"]
TIKTOK_CLIENT_KEY=xxx
TIKTOK_CLIENT_SECRET=xxx
INSTAGRAM_APP_ID=xxx
INSTAGRAM_APP_SECRET=xxx
YOUTUBE_API_KEY=xxx
```

**Frontend service:**
```
VITE_API_URL=https://tu-backend.railway.app/api
```

### 4. Deploy
```bash
git push origin main
```

¡Listo! Railway automáticamente:
- ✅ Detecta cambios
- ✅ Build Docker containers
- ✅ Crea PostgreSQL & Redis
- ✅ Deploy de todos los servicios
- ✅ Da URLs públicas

---

## URLs finales

Después de deploy, Railway te da:

| Servicio | URL |
|----------|-----|
| Frontend | `https://youtube-clip-gen-frontend-xxx.railway.app` |
| Backend API | `https://youtube-clip-gen-backend-xxx.railway.app` |
| API Docs | `https://youtube-clip-gen-backend-xxx.railway.app/docs` |

---

## Verificar que funciona

```bash
# Check backend
curl https://youtube-clip-gen-backend-xxx.railway.app/health

# Abrir en browser
https://youtube-clip-gen-frontend-xxx.railway.app
```

---

## Primeros pasos después del deploy

1. **Registro en la app**
   - Frontend → Register
   - Crear usuario test

2. **Obtener API credentials**
   - [YouTube API](https://console.cloud.google.com)
   - [TikTok Dev](https://developers.tiktok.com)
   - [Instagram Graph API](https://developers.facebook.com)

3. **Configurar en Railway dashboard**
   - Backend service → Variables → Añadir las credenciales

4. **Test upload**
   - Paste YouTube URL
   - ¡Mira cómo genera clips!

---

## Solucionar problemas

| Problema | Solución |
|----------|----------|
| Backend no inicia | Revisa logs en Railway dashboard |
| Frontend no conecta | Verifica `VITE_API_URL` correcta |
| Clips no generan | Chequea que Redis y Celery corren (logs) |
| Error de DB | PostgreSQL necesita `DATABASE_URL` correcta |

---

## Próximos pasos

- [ ] Hacer push a GitHub
- [ ] Crear cuenta en Railway
- [ ] Conectar GitHub a Railway
- [ ] Añadir environment variables
- [ ] Esperar ~5 min a que haga build
- [ ] Abrir URL del frontend
- [ ] Registrarse y probar

**¿Listo?** Empieza con el `git push`
