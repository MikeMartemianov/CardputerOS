#!/usr/bin/env python3
"""
CardputerOS YouTube Server — Chromium on Render
Uses system Chromium (no cookies needed — YouTube sees real browser)
"""

import os
import json
import time
import subprocess
import threading
import urllib.request
import urllib.parse
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

MJPEG_FPS = 15
MJPEG_QUALITY = 60
MJPEG_WIDTH = 240
MJPEG_HEIGHT = 135

# ============================================================
# Find Chromium executable
# ============================================================
CHROMIUM_PATH = None  # Let Playwright use its own bundled Chromium
print("[OK] Chromium: Playwright bundled")

# ============================================================
# Video extraction with Playwright + system Chromium
# ============================================================
class VideoExtractor:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
    
    def get_video_url(self, video_id):
        """Get video stream URL using real Chromium browser"""
        with self._lock:
            if video_id in self._cache:
                cached = self._cache[video_id]
                if time.time() - cached.get('time', 0) < 3600:
                    return cached
        
        try:
            from playwright.sync_api import sync_playwright
            
            video_urls = []
            
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-setuid-sandbox',
                        '--single-process',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ]
                )
                
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                )
                
                # Remove webdriver detection
                page = context.new_page()
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    window.chrome = { runtime: {} };
                """)
                
                def on_response(response):
                    url = response.url
                    if 'googlevideo.com/videoplayback' in url:
                        video_urls.append(url)
                
                page.on('response', on_response)
                
                print(f"[Chromium] Loading video {video_id}...")
                page.goto(f'https://www.youtube.com/watch?v={video_id}',
                         wait_until='domcontentloaded', timeout=25000)
                
                # Accept consent if present
                try:
                    page.locator('button:has-text("Accept all"), button:has-text("Принять все"), button:has-text("Reject all")').first.click(timeout=3000)
                    time.sleep(2)
                except:
                    pass
                
                # Wait for video to load
                time.sleep(5)
                
                # Click play
                try:
                    page.locator('.ytp-large-play-button, .ytp-play-button, button[aria-label*="Play"]').first.click(timeout=5000)
                    time.sleep(5)
                except:
                    pass
                
                # Get title
                title = page.title().replace(' - YouTube', '')
                
                # Get duration
                duration = 0
                try:
                    dur_text = page.locator('.ytp-time-duration').inner_text(timeout=3000)
                    parts = dur_text.split(':')
                    if len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                except:
                    pass
                
                print(f"[Chromium] Found {len(video_urls)} video URLs, title={title[:50]}")
                browser.close()
            
            # Pick best URL
            video_url = None
            for url in video_urls:
                if 'itag=18' in url:  # 360p MP4 with audio
                    video_url = url
                    break
            if not video_url and video_urls:
                video_url = video_urls[0]
            
            if video_url:
                with self._lock:
                    self._cache[video_id] = {
                        'url': video_url,
                        'title': title,
                        'duration': duration,
                        'time': time.time(),
                    }
                return self._cache[video_id]
            
            return None
            
        except Exception as e:
            print(f"[Chromium] Error: {e}")
            return None

extractor = VideoExtractor()

# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/scan')
def api_scan():
    return jsonify({
        'status': 'ok', 'version': '3.0',
        'name': 'CardputerOS YouTube Server (Chromium)',
        'chromium': 'Playwright bundled',
        'mjpeg_fps': MJPEG_FPS,
        'mjpeg_resolution': f'{MJPEG_WIDTH}x{MJPEG_HEIGHT}',
    })

@app.route('/api/debug/<video_id>')
def api_debug(video_id):
    info = extractor.get_video_url(video_id)
    if info:
        return jsonify({
            'status': 'ok',
            'title': info.get('title', '?'),
            'duration': info.get('duration', 0),
            'url': info.get('url', '')[:120],
        })
    return jsonify({'status': 'error', 'error': 'Chromium could not extract video URL. Check Render logs for details.'})

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    try:
        url = f'https://api.piped.private.coffee/search?q={urllib.parse.quote(query)}&filter=videos'
        req = urllib.request.Request(url, headers={'User-Agent': 'CardputerOS/3.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            results = []
            for item in data.get('items', [])[:10]:
                vid = item.get('url', '').replace('/watch?v=', '')
                if vid:
                    results.append({
                        'id': vid,
                        'title': item.get('title', '?')[:64],
                        'duration': f"{item.get('duration', 0)//60}:{item.get('duration', 0)%60:02d}",
                        'views': f"{item.get('views', 0):,}",
                    })
            return jsonify(results)
    except:
        return jsonify([])

@app.route('/api/stream/<video_id>')
def api_stream(video_id):
    info = extractor.get_video_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404
    
    video_url = info['url']
    
    def generate_mjpeg():
        cmd = [
            'ffmpeg', '-re', '-i', video_url,
            '-f', 'mjpeg',
            '-vf', f'scale={MJPEG_WIDTH}:{MJPEG_HEIGHT}',
            '-r', str(MJPEG_FPS), '-q:v', str(MJPEG_QUALITY),
            '-an', 'pipe:1'
        ]
        process = None
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=65536
            )
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                pos = 0
                while pos < len(chunk):
                    soi = chunk.find(b'\xff\xd8', pos)
                    if soi == -1:
                        break
                    eoi = chunk.find(b'\xff\xd9', soi)
                    if eoi == -1:
                        break
                    frame = chunk[soi:eoi+2]
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    pos = eoi + 2
        except Exception as e:
            print(f"MJPEG error: {e}")
        finally:
            if process:
                process.terminate()
    
    return Response(
        generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'}
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting CardputerOS YouTube Server (Chromium) on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
