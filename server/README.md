# CardputerOS - YouTube Companion Server

## What is this?
This Python server runs on your PC/laptop and acts as a bridge between YouTube and the Cardputer.
It transcodes YouTube videos into MJPEG streams that the ESP32 can decode and display.

## Requirements
- Python 3.8+
- yt-dlp (YouTube video extraction)
- ffmpeg (video transcoding)

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Make sure ffmpeg is installed and in PATH
# Windows: download from https://ffmpeg.org/download.html
# Linux: sudo apt install ffmpeg
# Mac: brew install ffmpeg
```

## Usage

```bash
# Start the server
python youtube_proxy.py

# The server will:
# 1. Start HTTP server on port 8080
# 2. Start UDP broadcast for auto-discovery on port 5353
# 3. Listen for video requests from Cardputer
```

## API Endpoints

### Scan (Health Check)
```
GET /api/scan
Response: 200 OK with JSON {"status": "ok", "version": "0.1.0"}
```

### Search YouTube
```
GET /api/search?q=<query>
Response: JSON array of video results
[
  {
    "id": "dQw4w9WgXcQ",
    "title": "Video Title",
    "thumbnail": "http://server:8080/api/thumb/dQw4w9WgXcQ",
    "duration": "3:33",
    "views": "1,234,567"
  }
]
```

### MJPEG Video Stream
```
GET /api/stream/<video_id>
Response: multipart/x-mixed-replace stream
Each part is a JPEG frame at 240x135 resolution
Frame rate: ~15 FPS
```

### Audio Stream
```
GET /api/audio/<video_id>
Response: audio/mpeg stream (MP3)
Sample rate: 22050 Hz, Mono
```

### Thumbnail
```
GET /api/thumb/<video_id>
Response: image/jpeg thumbnail
```

### Play by URL
```
POST /api/play
Body: {"url": "https://www.youtube.com/watch?v=XXXX"}
Response: {"status": "playing", "video_id": "XXXX"}
```

## How It Works

```
Cardputer                    PC Server                    YouTube
   |                            |                            |
   |-- GET /api/stream/VID ---->|                            |
   |                            |-- yt-dlp get stream URL -->|
   |                            |<--- direct video URL ------|
   |                            |-- ffmpeg transcode ------->|
   |<---- MJPEG frames ---------|<--- video stream ----------|
   |                            |                            |
```

## Configuration
Edit the top of youtube_proxy.py to change:
- SERVER_PORT (default: 8080)
- MJPEG_FPS (default: 15)
- MJPEG_QUALITY (default: 60, JPEG quality 1-100)
- MJPEG_WIDTH (default: 240)
- MJPEG_HEIGHT (default: 135)

## Troubleshooting

### "ffmpeg not found"
Make sure ffmpeg is installed and accessible from command line.
Run: `ffmpeg -version` to verify.

### "yt-dlp not found"
Install: `pip install yt-dlp`

### Cardputer can't find server
- Make sure both devices are on the same WiFi network
- Check firewall settings (port 8080 and 5353 UDP)
- Try entering the server IP manually in CardputerOS Settings

### Video is choppy
- Reduce MJPEG_FPS in server config
- Reduce MJPEG_QUALITY
- Make sure WiFi signal is strong
- Close other bandwidth-heavy applications
