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
AUDIO_SAMPLE_RATE = 22050

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(SERVER_DIR, 'cookies.txt')

# ============================================================
# Video Cache
# ============================================================
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

        # Strategy 1: Piped API (fastest, no browser needed)
        result = self._try_piped(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        # Strategy 2: yt-dlp with cookies (reliable)
        result = self._try_ytdlp(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        # Strategy 3: Playwright (last resort)
        result = self._try_playwright(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        return None

    def _cache_and_return(self, video_id, result):
        result['time'] = time.time()
        with self._lock:
            self._cache[video_id] = result
        return result

    # ----------------------------------------------------------
    # Strategy 1: Piped API
    # ----------------------------------------------------------
    def _try_piped(self, video_id):
        piped_instances = [
            'https://api.pipedapi.adminforge.de',
            'https://pipedapi.r4fo.com',
            'https://watchapi.whatever.social',
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
                    print(f"[Piped] {instance} error: {data['error']}")
                    continue

                video_url = None
                # Prefer streams with audio
                for stream in data.get('videoStreams', []):
                    if not stream.get('videoOnly', True):
                        video_url = stream.get('url')
                        break
                # Fallback to any video stream
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
                continue
        return None

    # ----------------------------------------------------------
    # Strategy 2: yt-dlp with cookies
    # ----------------------------------------------------------
    def _try_ytdlp(self, video_id):
        try:
            import yt_dlp
        except ImportError:
            print("[yt-dlp] Not installed, skipping")
            return None

        cookies_exist = os.path.exists(COOKIES_PATH)
        cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0

        ydl_opts = {
            'format': 'worst[ext=mp4]/worst',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            },
        }

        if cookies_exist and cookies_size > 50:
            ydl_opts['cookies'] = COOKIES_PATH
            print(f"[yt-dlp] Using cookies ({cookies_size} bytes)")
        else:
            print(f"[yt-dlp] No valid cookies (exists={cookies_exist}, size={cookies_size})")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False,
                )

                if 'url' in info:
                    video_url = info['url']
                elif 'formats' in info and info['formats']:
                    formats = sorted(
                        info['formats'],
                        key=lambda f: f.get('height', 9999),
                    )
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

    # ----------------------------------------------------------
    # Strategy 3: Playwright with cookies
    # ----------------------------------------------------------
    def _try_playwright(self, video_id):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[Playwright] Not installed, skipping")
            return None

        try:
            video_urls = []

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ],
                )

                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/131.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                )

                # Load cookies from cookies.txt (Netscape format)
                self._load_cookies(context)

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

                print(f"[Playwright] Loading video {video_id}...")
                page.goto(
                    f'https://www.youtube.com/watch?v={video_id}',
                    wait_until='domcontentloaded',
                    timeout=25000,
                )

                # Accept consent if present
                try:
                    page.locator(
                        'button:has-text("Accept all"), '
                        'button:has-text("Принять все"), '
                        'button:has-text("Reject all")'
                    ).first.click(timeout=3000)
                    time.sleep(2)
                except Exception:
                    pass

                # Wait for video to load
                time.sleep(5)

                # Click play
                try:
                    page.locator(
                        '.ytp-large-play-button, '
                        '.ytp-play-button, '
                        'button[aria-label*="Play"]'
                    ).first.click(timeout=5000)
                    time.sleep(5)
                except Exception:
                    pass

                title = page.title().replace(' - YouTube', '')
                duration = self._extract_duration(page)

                print(f"[Playwright] Found {len(video_urls)} video URLs, title={title[:50]}")
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
                return {
                    'url': video_url,
                    'title': title,
                    'duration': duration,
                    'source': 'playwright',
                }

        except Exception as e:
            print(f"[Playwright] Error: {e}")
            traceback.print_exc()

        return None

    def _load_cookies(self, context):
        """Load cookies from Netscape format cookies.txt into Playwright context"""
        if not os.path.exists(COOKIES_PATH):
            print("[Playwright] No cookies.txt found")
            return

        cookies = []
        try:
            with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('\t')
                    if len(parts) < 7:
                        continue
                    domain, _, path, secure, expires, name, value = parts[:7]
                    cookie = {
                        'name': name,
                        'value': value,
                        'domain': domain,
                        'path': path,
                        'secure': secure.upper() == 'TRUE',
                        'httpOnly': False,
                    }
                    if expires and expires != '0':
                        try:
                            cookie['expires'] = int(expires)
                        except ValueError:
                            pass
                    cookies.append(cookie)
        except Exception as e:
            print(f"[Playwright] Cookie parse error: {e}")
            return

        if cookies:
            try:
                context.add_cookies(cookies)
                print(f"[Playwright] Loaded {len(cookies)} cookies")
            except Exception as e:
                print(f"[Playwright] Cookie load error: {e}")

    @staticmethod
    def _extract_duration(page):
        try:
            dur_text = page.locator('.ytp-time-duration').inner_text(timeout=3000)
            parts = dur_text.split(':')
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except Exception:
            pass
        return 0


extractor = VideoExtractor()

# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/scan')
def api_scan():
    cookies_exist = os.path.exists(COOKIES_PATH)
    cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0
    return jsonify({
        'status': 'ok',
        'version': '4.0',
        'name': 'CardputerOS YouTube Server',
        'strategies': ['piped', 'yt-dlp', 'playwright'],
        'cookies': f'{cookies_size} bytes' if cookies_exist else 'missing',
        'mjpeg_fps': MJPEG_FPS,
        'mjpeg_resolution': f'{MJPEG_WIDTH}x{MJPEG_HEIGHT}',
    })


@app.route('/api/debug/<video_id>')
def api_debug(video_id):
    info = extractor.get_video_url(video_id)
    if info:
        return jsonify({
            'status': 'ok',
            'source': info.get('source', '?'),
            'title': info.get('title', '?'),
            'duration': info.get('duration', 0),
            'url': info.get('url', '')[:120],
        })
    return jsonify({
        'status': 'error',
        'error': 'All extraction strategies failed. Check Render logs.',
    })


@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    piped_instances = [
        'https://api.pipedapi.adminforge.de',
        'https://api.piped.private.coffee',
        'https://pipedapi.r4fo.com',
    ]

    for instance in piped_instances:
        try:
            url = f'{instance}/search?q={urllib.parse.quote(query)}&filter=videos'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'CardputerOS/4.0',
                'Accept': 'application/json',
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                results = []
                for item in data.get('items', [])[:10]:
                    vid = item.get('url', '').replace('/watch?v=', '')
                    if vid:
                        results.append({
                            'id': vid,
                            'title': item.get('title', '?')[:64],
                            'duration': f"{item.get('duration', 0) // 60}:{item.get('duration', 0) % 60:02d}",
                            'views': f"{item.get('views', 0):,}",
                        })
                if results:
                    return jsonify(results)
        except Exception as e:
            print(f"[Search] {instance} failed: {e}")
            continue

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
            '-an', 'pipe:1',
        ]
        process = None
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=65536,
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
                    frame = chunk[soi:eoi + 2]
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                           + frame + b'\r\n')
                    pos = eoi + 2
        except Exception as e:
            print(f"MJPEG error: {e}")
        finally:
            if process:
                process.terminate()

    return Response(
        generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
    )


@app.route('/api/audio/<video_id>')
def api_audio(video_id):
    info = extractor.get_video_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404

    video_url = info['url']

    def generate_audio():
        cmd = [
            'ffmpeg', '-i', video_url,
            '-f', 'mp3',
            '-ar', str(AUDIO_SAMPLE_RATE),
            '-ac', '1',
            '-ab', '64k',
            '-vn', 'pipe:1',
        ]
        process = None
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            while True:
                data = process.stdout.read(4096)
                if not data:
                    break
                yield data
        except Exception as e:
            print(f"Audio stream error: {e}")
        finally:
            if process:
                process.terminate()

    return Response(
        generate_audio(),
        mimetype='audio/mpeg',
        headers={'Cache-Control': 'no-cache', 'Transfer-Encoding': 'chunked'},
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 50)
    print("  CardputerOS YouTube Server v4.0")
    print("=" * 50)
    cookies_exist = os.path.exists(COOKIES_PATH)
    cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0
    print(f"  Cookies: {'OK' if cookies_exist and cookies_size > 50 else 'MISSING'} ({cookies_size} bytes)")
    print(f"  Strategies: Piped API -> yt-dlp -> Playwright")
    print(f"  Port: {port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
