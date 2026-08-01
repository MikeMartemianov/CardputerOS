# CardputerOS - Deep Analysis: YouTube Streaming

## Problem Statement
User wants to play YouTube videos on M5Stack Cardputer (ESP32-S3FN8, 240x135 screen, no PSRAM).

## Hardware Constraints
- ESP32-S3FN8: 512KB SRAM, 8MB Flash, NO PSRAM
- Display: 240x135 ST7789V2 via SPI
- WiFi: 2.4GHz only
- No hardware H.264/H.265 decoder
- CPU: Dual-core 240MHz Xtensa LX7

## Why Not Chromium/WebView?
- User explicitly rejected Chromium as "too inefficient"
- ESP32-S3 cannot run any browser engine
- No RAM for DOM rendering

## YouTube Video Format Analysis
YouTube serves video via DASH (Dynamic Adaptive Streaming over HTTP):
- Containers: fMP4, WebM
- Video codecs: H.264 (AVC), VP9, AV1
- Audio codecs: AAC, Opus, MP3
- Resolution: 144p to 8K
- No direct MJPEG stream available

## ESP32-S3 Video Decoding Capabilities
- JPEG: Hardware JPEG decoder (via TJpgDec library, DMA-accelerated)
- MJPEG: Can decode ~10-20 FPS at 240x135
- H.264: NO hardware decoder, software decode too slow
- VP9: NO hardware decoder
- AV1: NO hardware decoder

## Solution Architecture: Companion Server

### Approach
A Python server runs on a PC/laptop in the same WiFi network.
It acts as a proxy between YouTube and the Cardputer.

### Server Pipeline
```
YouTube URL
  -> yt-dlp extracts direct video URL
  -> ffmpeg transcodes to MJPEG stream at 240x135
  -> HTTP server serves MJPEG stream
  -> Cardputer connects and displays frames

YouTube URL
  -> yt-dlp extracts audio URL
  -> ffmpeg transcodes to PCM/I2S format
  -> HTTP server serves audio stream
  -> Cardputer plays via I2S speaker
```

### Server Endpoints
1. `GET /api/scan` - Discover servers on local network (UDP broadcast)
2. `GET /api/search?q=<query>` - Search YouTube, return results JSON
3. `GET /api/stream/<video_id>` - MJPEG stream, 240x135, ~15fps
4. `GET /api/audio/<video_id>` - Audio stream, 22050Hz mono
5. `GET /api/thumb/<video_id>` - Thumbnail JPEG
6. `POST /api/play` - Start playing a video by URL

### Cardputer Client
1. Connect to WiFi
2. Discover server via UDP broadcast (or manual IP entry)
3. Request video stream
4. Decode JPEG frames via TJpgDec
5. Push to display via SPI DMA
6. Simultaneously stream audio via I2S

### Performance Estimates
- WiFi throughput: ~2-5 Mbps (2.4GHz, realistic)
- JPEG frame at 240x135: ~3-8 KB
- At 10 FPS: 30-80 KB/s = 240-640 Kbps (fits in WiFi budget)
- Audio at 22050Hz 8-bit mono: ~22 KB/s = 176 Kbps
- Total: ~400-800 Kbps (well within WiFi capacity)

## Alternative Approaches Considered

### 1. Direct YouTube API on ESP32
- YouTube Data API v3 for metadata (works)
- But video streams require DASH client (too complex for ESP32)
- REJECTED: Too complex, no real-time decoding

### 2. Invidious Instance
- Invidious provides direct stream URLs
- But still serves H.264/VP9 which ESP32 cannot decode
- PARTIALLY USEFUL: For metadata/search, not video playback

### 3. VLC/ffmpeg on Phone as Server
- Phone runs VLC HTTP stream server
- Cardputer connects to phone's MJPEG stream
- REJECTED: Too many moving parts

### 4. Server-side JPEG frame extraction
- Extract every Nth frame as JPEG
- Serve as HTTP multipart stream
- ACCEPTED: This is our primary approach

## Conclusion
The only realistic approach for YouTube on Cardputer is a companion server that
transcodes video to MJPEG in real-time. This provides:
- Smooth video playback at 10-15 FPS
- Low bandwidth requirements
- Compatible with ESP32-S3 hardware capabilities
- No need for heavy browser engine
