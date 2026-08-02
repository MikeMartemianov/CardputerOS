FROM python:3.11-slim

# Install ffmpeg and nodejs (needed for yt-dlp JS runtime)
RUN apt-get update && apt-get install -y ffmpeg nodejs && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy server code
COPY server/ /app/
WORKDIR /app

EXPOSE 8080

CMD ["python", "youtube_proxy.py"]
