#!/usr/bin/env python3
"""
CardputerOS YouTube Server v2 — Chromium-based
Uses Playwright (Chromium) instead of yt-dlp.
YouTube sees a real browser, no bot detection.

Usage:
    pip install flask playwright
    playwright install chromium
    python youtube_chromium.py
"""

import os
import json
import time
import subprocess
import threading
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

MJPEG_FPS = 15
MJPEG_QUALITY = 60
MJPEG_WIDTH = 240
MJPEG_HEIGHT = 135
AUDIO_SAMPLE_RATE = 22050

# ============================================================
# Chromium-based video URL extraction
# ============================================================
class ChromiumExtractor:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._browser = None
        self._playwright = None
        self._context = None
    
    def _ensure_browser(self):
        if self._browser and self._browser.is_connected():
            return
        try:
            from playwright.sync_api import sync_playwright
            if not self._playwright:
                self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            self._context = self._browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            # Accept YouTube consent
            page = self._context.new_page()
            page.goto('https://www.youtube.com', wait_until='domcontentloaded', timeout=15000)
            try:
                accept_btn = page.locator('button:has-text("Accept all"), button:has-text("Принять все")')
                if accept_btn.count() > 0:
                    accept_btn.first.click(timeout=3000)
                    time.sleep(1)
            except:
                pass
            page.close()
            print("[Chromium] Browser ready")
        except Exception as e:
            print(f"[Chromium] Error: {e}")
    
    def get_video_url(self, video_id):
        """Get direct video stream URL using Chromium"""
        with self._lock:
            if video_id in self._cache:
                cached = self._cache[video_id]
                if time.time() - cached.get('time', 0) < 3600:
                    return cached
        
        try:
            self._ensure_browser()
            
            video_urls = []
            audio_urls = []
            
            def handle_response(response):
                url = response.url
                if 'googlevideo.com/videoplayback' in url:
                    video_urls.append(url)
            
            page = self._context.new_page()
            page.on('response', handle_response)
            
            # Navigate to video
            page.goto(f'https://www.youtube.com/watch?v={video_id}', 
                     wait_until='domcontentloaded', timeout=30000)
            
            # Wait for video to start loading
            time.sleep(5)
            
            # Try to click play if needed
            try:
                page.locator('.ytp-large-play-button, .ytp-play-button').first.click(timeout=3000)
                time.sleep(3)
            except:
                pass
            
            # Wait for network requests
            time.sleep(3)
            
            # Get title
            title = page.title()
            if ' - YouTube' in title:
                title = title.replace(' - YouTube', '')
            
            # Get duration from page
            try:
                duration_text = page.locator('.ytp-time-duration').inner_text(timeout=3000)
                parts = duration_text.split(':')
                if len(parts) == 2:
                    duration = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                else:
                    duration = 0
            except:
                duration = 0
            
            page.close()
            
            # Use the best URL found
            video_url = None
            if video_urls:
                # Prefer itag=18 (360p mp4 with audio)
                for url in video_urls:
                    if 'itag=18' in url:
                        video_url = url
                        break
                if not video_url:
                    video_url = video_urls[0]
            
            if not video_url and audio_urls:
                video_url = audio_urls[0]
            
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
            print(f"[Chromium] Error for {video_id}: {e}")
            return None
    
    def close(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

extractor = ChromiumExtractor()

# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/scan')
def api_scan():
    return jsonify({
        'status': 'ok', 'version': '2.0',
        'name': 'CardputerOS YouTube Server (Chromium)',
        'mjpeg_fps': MJPEG_FPS, 'mjpeg_quality': MJPEG_QUALITY,
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
            'url': info.get('url', 'NONE')[:150],
        })
    return jsonify({'status': 'error', 'error': 'Video not found or blocked'})

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
                # Extract JPEG frames
                pos = 0
                while pos < len(chunk):
                    # Find JPEG SOI (FFD8)
                    soi = chunk.find(b'\xff\xd8', pos)
                    if soi == -1:
                        break
                    # Find JPEG EOI (FFD9)
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

@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    # Use Piped for search (lightweight, no browser needed)
    import urllib.request, urllib.parse
    try:
        url = f'https://api.piped.private.coffee/search?q={urllib.parse.quote(query)}&filter=videos'
        req = urllib.request.Request(url, headers={'User-Agent': 'CardputerOS/2.0'})
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting CardputerOS YouTube Server (Chromium) on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
