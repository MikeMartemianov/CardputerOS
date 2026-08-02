#!/usr/bin/env python3
"""
CardputerOS YouTube Server v4.0 — Multi-strategy extraction
Strategy 1: Piped API (lightweight, fast)
Strategy 2: yt-dlp with cookies (reliable)
Strategy 3: Playwright + cookies (fallback)
"""

import os
import json
import time
import subprocess
import threading
import traceback
import urllib.request
import urllib.parse
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

MJPEG_FPS = 15
MJPEG_QUALITY = 60
MJPEG_WIDTH = 240
MJPEG_HEIGHT = 135

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(SERVER_DIR, 'cookies.txt')


class VideoExtractor:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def _is_cache_valid(self, entry):
        return entry and (time.time() - entry.get('time', 0)) < 3600

    def get_video_url(self, video_id):
        with self._lock:
            if video_id in self._cache and self._is_cache_valid(self._cache[video_id]):
                return self._cache[video_id]

        result = self._try_piped(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        result = self._try_ytdlp(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        result = self._try_playwright(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        return None

    def _cache_and_return(self, video_id, result):
        result['time'] = time.time()
        with self._lock:
            self._cache[video_id] = result
        return result

    def _try_piped(self, video_id):
        piped_instances = [
            'https://api.pipedapi.adminforge.de',
            'https://pipedapi.r4fo.com',
        ]
        for instance in piped_instances:
            try:
                url = f'{instance}/streams/{video_id}'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'CardputerOS/4.0',
                    'Accept': 'application/json',
                })
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read())
                if 'error' in data:
                    continue
                video_url = None
                for stream in data.get('videoStreams', []):
                    if not stream.get('videoOnly', True):
                        video_url = stream.get('url')
                        break
                if not video_url and data.get('videoStreams'):
                    video_url = data['videoStreams'][0].get('url')
                if video_url:
                    print(f"[Piped] Success via {instance}")
                    return {
                        'url': video_url,
                        'title': data.get('title', 'Unknown'),
                        'duration': data.get('duration', 0),
                        'source': 'piped',
                    }
            except Exception as e:
                print(f"[Piped] {instance} failed: {e}")
        return None

    def _try_ytdlp(self, video_id):
        try:
            import yt_dlp
        except ImportError:
            return None

        cookies_exist = os.path.exists(COOKIES_PATH)
        cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0
        ydl_opts = {
            'format': 'worst[ext=mp4]/worst',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
        }
        if cookies_exist and cookies_size > 50:
            ydl_opts['cookies'] = COOKIES_PATH

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
                if 'url' in info:
                    video_url = info['url']
                elif 'formats' in info and info['formats']:
                    formats = sorted(info['formats'], key=lambda f: f.get('height', 9999))
                    video_url = formats[0]['url']
                else:
                    return None
                print(f"[yt-dlp] Success")
                return {
                    'url': video_url,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'source': 'yt-dlp',
                }
        except Exception as e:
            print(f"[yt-dlp] Error: {e}")
            return None

    def _try_playwright(self, video_id):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None
        try:
            video_urls = []
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'])
                context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
                self._load_cookies(context)
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => false });")
                def on_response(response):
                    if 'googlevideo.com/videoplayback' in response.url:
                        video_urls.append(response.url)
                page.on('response', on_response)
                page.goto(f'https://www.youtube.com/watch?v={video_id}', wait_until='domcontentloaded', timeout=25000)
                time.sleep(5)
                try:
                    page.locator('.ytp-large-play-button, .ytp-play-button').first.click(timeout=5000)
                    time.sleep(5)
                except Exception:
                    pass
                title = page.title().replace(' - YouTube', '')
                browser.close()
            video_url = None
            for url in video_urls:
                if 'itag=18' in url:
                    video_url = url
                    break
            if not video_url and video_urls:
                video_url = video_urls[0]
            if video_url:
                return {'url': video_url, 'title': title, 'duration': 0, 'source': 'playwright'}
        except Exception as e:
            print(f"[Playwright] Error: {e}")
        return None

    def _load_cookies(self, context):
        if not os.path.exists(COOKIES_PATH):
            return
        cookies = []
        try:
            with open(COOKIES_PATH, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('\t')
                    if len(parts) < 7:
                        continue
                    domain, _, path, secure, expires, name, value = parts[:7]
                    cookie = {'name': name, 'value': value, 'domain': domain, 'path': path, 'secure': secure.upper() == 'TRUE', 'httpOnly': False}
                    if expires and expires != '0':
                        try:
                            cookie['expires'] = int(expires)
                        except ValueError:
                            pass
                    cookies.append(cookie)
        except Exception:
            return
        if cookies:
            try:
                context.add_cookies(cookies)
            except Exception:
                pass


extractor = VideoExtractor()


@app.route('/api/scan')
def api_scan():
    return jsonify({'status': 'ok', 'version': '4.0', 'name': 'CardputerOS YouTube Server'})


@app.route('/api/debug/<video_id>')
def api_debug(video_id):
    info = extractor.get_video_url(video_id)
    if info:
        return jsonify({'status': 'ok', 'source': info.get('source', '?'), 'title': info.get('title', '?'), 'duration': info.get('duration', 0), 'url': info.get('url', '')[:120]})
    return jsonify({'status': 'error', 'error': 'All extraction strategies failed.'})


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    for instance in ['https://api.pipedapi.adminforge.de', 'https://pipedapi.r4fo.com']:
        try:
            req = urllib.request.Request(f'{instance}/search?q={urllib.parse.quote(query)}&filter=videos', headers={'User-Agent': 'CardputerOS/4.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                results = []
                for item in data.get('items', [])[:10]:
                    vid = item.get('url', '').replace('/watch?v=', '')
                    if vid:
                        results.append({'id': vid, 'title': item.get('title', '?')[:64], 'duration': f"{item.get('duration', 0)//60}:{item.get('duration', 0)%60:02d}", 'views': f"{item.get('views', 0):,}"})
                if results:
                    return jsonify(results)
        except Exception:
            continue
    return jsonify([])


@app.route('/api/stream/<video_id>')
def api_stream(video_id):
    info = extractor.get_video_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404
    video_url = info['url']

    def generate_mjpeg():
        cmd = ['ffmpeg', '-re', '-i', video_url, '-f', 'mjpeg', '-vf', f'scale={MJPEG_WIDTH}:{MJPEG_HEIGHT}', '-r', str(MJPEG_FPS), '-q:v', str(MJPEG_QUALITY), '-an', 'pipe:1']
        process = None
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=65536)
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
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + chunk[soi:eoi+2] + b'\r\n')
                    pos = eoi + 2
        except Exception as e:
            print(f"MJPEG error: {e}")
        finally:
            if process:
                process.terminate()

    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame', headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
