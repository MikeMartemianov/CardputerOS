FROM python:3.11-slim

# Install Node.js (required by yt-dlp for YouTube JS challenges)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && node --version && npm --version \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (yt-dlp[default] includes EJS challenge solver scripts)
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Verify yt-dlp and EJS
RUN python -c "import yt_dlp; print('yt-dlp', yt_dlp.version.__version__)" && \
    python -c "from yt_dlp import _version; print('OK')"

# Copy server code
COPY server/ /app/
WORKDIR /app

EXPOSE 8080

CMD ["python", "youtube_chromium.py"]
