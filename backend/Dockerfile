FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp needs a JavaScript runtime to solve YouTube's "n challenge".
# Without it, extraction degrades and can return no downloadable formats.
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- -y \
    && deno --version

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
