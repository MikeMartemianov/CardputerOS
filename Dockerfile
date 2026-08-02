FROM python:3.11-slim

# Install system deps for Chromium
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libxkbcommon0 \
    fonts-liberation \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (for caching)
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright + Chromium (bundled, not system)
RUN playwright install --with-deps chromium

# Copy server code
COPY server/ /app/
WORKDIR /app

EXPOSE 8080

CMD ["python", "youtube_chromium.py"]
