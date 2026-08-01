# CardputerOS - Evolution Log

## v0.1.0 - Initial Architecture (2026-08-01)

### Research Phase
- Discovered Cardputer uses ESP32-S3FN8 (NO PSRAM!)
- This is a critical hardware limitation
- YouTube playback requires companion server approach
- MJPEG streaming is the only realistic video format

### Architecture Decisions
1. **Companion Server for YouTube**: Python server with yt-dlp + ffmpeg transcodes to MJPEG
2. **Mouse Cursor via Keyboard**: FN+M toggles mouse mode, arrows move, Enter clicks
3. **Single Frame Buffer**: No PSRAM means only one 65KB frame buffer
4. **JPEG-only Video**: TJpgDec hardware-accelerated JPEG decoding

### Files Created
- platformio.ini - PlatformIO config for ESP32-S3
- include/config.h - All constants and pin definitions
- include/hal.h - Hardware abstraction layer
- include/mouse.h - Mouse cursor system
- include/events.h - Event queue system
- include/gui.h - GUI widgets and window management
- include/youtube.h - YouTube player interface
- src/main.cpp - OS boot and main loop
- src/system/hal.cpp - Hardware init and control
- src/input/mouse.cpp - Mouse cursor implementation
- src/input/events.cpp - Event ring buffer
- src/apps/youtube.cpp - YouTube player app
- server/youtube_proxy.py - Python companion server

### Lessons Learned
1. Always check chip variant before assuming PSRAM availability
2. ESP32-S3FN8 does NOT have PSRAM (F=QFN, N=no PSRAM, 8=8MB flash)
3. MJPEG is the only realistic video format for ESP32 without PSRAM
4. Companion server approach is standard for YouTube on ESP32
5. LovyanGFX/M5GFX provides hardware-accelerated JPEG decoding
