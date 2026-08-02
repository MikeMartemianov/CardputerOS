FROM python:3.11-slim

# Install ffmpeg and Chromium + dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    chromium \
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
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install Playwright browsers (will use system chromium)
ENV PLAYWRIGHT_BROWSERS_PATH=0
RUN playwright install chromium || true

# Copy server code
COPY server/ /app/
WORKDIR /app

EXPOSE 8080

CMD ["python", "youtube_chromium.py"]
