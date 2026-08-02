#!/usr/bin/env python3
"""
CardputerOS YouTube Server v5.0 — Direct extraction, no third-party deps
Strategy 1: YouTube Innertube API (direct, lightweight, most reliable)
Strategy 2: yt-dlp with cookies (proven to work)
Strategy 3: Piped API instances (if any are alive)
Strategy 4: Playwright + cookies (last resort)
"""

import hashlib
import http.cookiejar
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
# YouTube Innertube constants
# ============================================================
INNERTUBE_API_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
INNERTUBE_SEARCH_URL = f'https://www.youtube.com/youtubei/v1/search?key={INNERTUBE_API_KEY}'

# Client configs — less restrictive clients get fewer bot checks
INNERTUBE_CLIENTS = [
    {
        'name': 'WEB',
        'clientName': 'WEB',
        'clientVersion': '2.20240801.00.00',
        'needs_auth': True,  # Works with SAPISID auth
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    },
    {
        'name': 'ANDROID',
        'clientName': 'ANDROID',
        'clientVersion': '19.29.37',
        'api_key': 'AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w',
        'user_agent': 'com.google.android.youtube/19.29.37 (Linux; U; Android 14; en_US) gzip',
    },
    {
        'name': 'MWEB',
        'clientName': 'MWEB',
        'clientVersion': '2.20240801.00.00',
        'needs_auth': True,
        'user_agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
    },
]

# ============================================================
# Cookie helpers
# ============================================================
def load_netscape_cookies(path):
    """Load Netscape format cookies.txt into a list of dicts"""
    cookies = []
    if not os.path.exists(path):
        return cookies
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) < 7:
                continue
            domain, _, path_val, secure, expires, name, value = parts[:7]
            cookies.append({
                'name': name,
                'value': value,
                'domain': domain,
                'path': path_val,
                'secure': secure.upper() == 'TRUE',
                'expires': int(expires) if expires and expires != '0' else -1,
            })
    return cookies


def cookies_to_header(cookies, domain='.youtube.com'):
    """Convert cookie list to Cookie header string"""
    parts = []
    for c in cookies:
        if domain in c['domain']:
            parts.append(f"{c['name']}={c['value']}")
    return '; '.join(parts)


def compute_sapisid_hash(sapisid, origin='https://www.youtube.com'):
    """Compute SAPISIDHASH authorization token"""
    ts = int(time.time())
    hash_input = f"{ts} {sapisid} {origin}"
    sha1 = hashlib.sha1(hash_input.encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{sha1}"


# ============================================================
# Video Cache
# ============================================================
class VideoExtractor:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._cookies = load_netscape_cookies(COOKIES_PATH)
        self._cookie_header = cookies_to_header(self._cookies)
        # Extract SAPISID for auth
        self._sapisid = None
        for c in self._cookies:
            if c['name'] == 'SAPISID':
                self._sapisid = c['value']
                break
        print(f"[Init] Loaded {len(self._cookies)} cookies, SAPISID={'YES' if self._sapisid else 'NO'}")

    def _is_cache_valid(self, entry):
        return entry and (time.time() - entry.get('time', 0)) < 3600

    def get_video_url(self, video_id):
        with self._lock:
            if video_id in self._cache and self._is_cache_valid(self._cache[video_id]):
                return self._cache[video_id]

        # Strategy 1: YouTube Innertube API (direct, no third-party)
        result = self._try_innertube(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        # Strategy 2: yt-dlp with cookies
        result = self._try_ytdlp(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        # Strategy 3: Piped API (most are dead, but worth trying)
        result = self._try_piped(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        # Strategy 4: Playwright (last resort)
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
    # Strategy 1: YouTube Innertube API (direct)
    # ----------------------------------------------------------
    def _try_innertube(self, video_id):
        for client in INNERTUBE_CLIENTS:
            try:
                payload = {
                    'context': {
                        'client': {
                            'clientName': client['clientName'],
                            'clientVersion': client['clientVersion'],
                        },
                    },
                    'videoId': video_id,
                }

                api_key = client.get('api_key', INNERTUBE_API_KEY)
                player_url = f'https://www.youtube.com/youtubei/v1/player?key={api_key}'

                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': client.get('user_agent',
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'),
                    'Origin': 'https://www.youtube.com',
                    'Referer': f'https://www.youtube.com/watch?v={video_id}',
                }

                # Add auth if client needs it and cookies are available
                if client.get('needs_auth'):
                    if self._sapisid:
                        headers['Authorization'] = compute_sapisid_hash(self._sapisid)
                    if self._cookie_header:
                        headers['Cookie'] = self._cookie_header
                elif self._cookie_header:
                    headers['Cookie'] = self._cookie_header

                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(player_url, data=data, headers=headers, method='POST')

                with urllib.request.urlopen(req, timeout=15) as resp:
                    body = json.loads(resp.read())

                # Check for errors
                status = body.get('playabilityStatus', {})
                if status.get('status') == 'ERROR':
                    print(f"[Innertube] {client['name']}: status=ERROR reason={status.get('reason', '?')[:80]}")
                    continue
                if status.get('status') == 'LOGIN_REQUIRED':
                    print(f"[Innertube] {client['name']}: LOGIN_REQUIRED")
                    continue
                if status.get('status') not in ('OK', None):
                    print(f"[Innertube] {client['name']}: status={status.get('status')} reason={status.get('reason', '')[:80]}")
                    continue

                # Extract streaming data
                streaming = body.get('streamingData', {})
                formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])

                if not formats:
                    print(f"[Innertube] {client['name']}: no formats")
                    continue

                # Find best format with audio (combined video+audio)
                video_url = None
                for fmt in formats:
                    if fmt.get('mimeType', '').startswith('video/') and 'url' in fmt:
                        has_audio = fmt.get('audioQuality') is not None
                        if has_audio:
                            video_url = fmt['url']
                            break

                # Fallback: any format with a direct URL
                if not video_url:
                    for fmt in formats:
                        if 'url' in fmt:
                            video_url = fmt['url']
                            break

                # Some formats use signatureCipher instead of direct URL
                if not video_url:
                    for fmt in formats:
                        if 'signatureCipher' in fmt:
                            print(f"[Innertube] {client['name']}: format needs signatureCipher (unsupported)")
                            break

                title = body.get('videoDetails', {}).get('title', 'Unknown')
                duration = int(body.get('videoDetails', {}).get('lengthSeconds', 0))

                if video_url:
                    print(f"[Innertube] Success via {client['name']}, title={title[:50]}")
                    return {
                        'url': video_url,
                        'title': title,
                        'duration': duration,
                        'source': f'innertube_{client["name"]}',
                    }
                else:
                    print(f"[Innertube] {client['name']}: no direct URL in {len(formats)} formats")

            except Exception as e:
                print(f"[Innertube] {client['name']}: {e}")
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
            print(f"[yt-dlp] No valid cookies")

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
    # Strategy 3: Piped API
    # ----------------------------------------------------------
    def _try_piped(self, video_id):
        piped_instances = [
            'https://api.pipedapi.adminforge.de',
            'https://api.piped.private.coffee',
            'https://pipedapi.r4fo.com',
        ]
        for instance in piped_instances:
            try:
                url = f'{instance}/streams/{video_id}'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'CardputerOS/5.0',
                    'Accept': 'application/json',
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
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
                continue
        return None

    # ----------------------------------------------------------
    # Strategy 4: Playwright with cookies
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
                    ],
                )

                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/131.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                )

                self._load_playwright_cookies(context)

                page = context.new_page()
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                    window.chrome = { runtime: {} };
                """)

                def on_response(response):
                    if 'googlevideo.com/videoplayback' in response.url:
                        video_urls.append(response.url)

                page.on('response', on_response)

                print(f"[Playwright] Loading video {video_id}...")
                page.goto(
                    f'https://www.youtube.com/watch?v={video_id}',
                    wait_until='domcontentloaded',
                    timeout=25000,
                )

                try:
                    page.locator(
                        'button:has-text("Accept all"), '
                        'button:has-text("Reject all")'
                    ).first.click(timeout=3000)
                    time.sleep(2)
                except Exception:
                    pass

                time.sleep(5)

                try:
                    page.locator('.ytp-large-play-button, .ytp-play-button').first.click(timeout=5000)
                    time.sleep(5)
                except Exception:
                    pass

                title = page.title().replace(' - YouTube', '')
                duration = self._extract_duration(page)

                print(f"[Playwright] Found {len(video_urls)} URLs")
                browser.close()

            video_url = None
            for url in video_urls:
                if 'itag=18' in url:
                    video_url = url
                    break
            if not video_url and video_urls:
                video_url = video_urls[0]

            if video_url:
                return {'url': video_url, 'title': title, 'duration': duration, 'source': 'playwright'}

        except Exception as e:
            print(f"[Playwright] Error: {e}")
        return None

    def _load_playwright_cookies(self, context):
        if not self._cookies:
            return
        pw_cookies = []
        for c in self._cookies:
            cookie = {
                'name': c['name'],
                'value': c['value'],
                'domain': c['domain'],
                'path': c['path'],
                'secure': c['secure'],
                'httpOnly': False,
            }
            if c['expires'] > 0:
                cookie['expires'] = c['expires']
            pw_cookies.append(cookie)
        try:
            context.add_cookies(pw_cookies)
            print(f"[Playwright] Loaded {len(pw_cookies)} cookies")
        except Exception as e:
            print(f"[Playwright] Cookie error: {e}")

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
# Search — YouTube Innertube search (direct) + Piped fallback
# ============================================================
def search_youtube_innertube(query):
    """Search via YouTube Innertube API — returns Piped-compatible format"""
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Origin': 'https://www.youtube.com',
        'Referer': 'https://www.youtube.com/results',
    }
    if extractor._sapisid and extractor._cookie_header:
        headers['Authorization'] = compute_sapisid_hash(extractor._sapisid)
        headers['Cookie'] = extractor._cookie_header
    elif extractor._cookie_header:
        headers['Cookie'] = extractor._cookie_header

    payload = {
        'context': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20240801.00.00',
            },
        },
        'query': query,
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(INNERTUBE_SEARCH_URL, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())

        results = []
        for item in body.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', []):
            for render in item.get('itemSectionRenderer', {}).get('contents', []):
                vid_renderer = render.get('videoRenderer', {})
                if not vid_renderer:
                    continue
                vid_id = vid_renderer.get('videoId', '')
                if not vid_id:
                    continue
                title_runs = vid_renderer.get('title', {}).get('runs', [])
                title = ''.join(r.get('text', '') for r in title_runs)
                length_text = vid_renderer.get('lengthText', {}).get('simpleText', '0:00')
                view_count_text = vid_renderer.get('viewCountText', {}).get('simpleText', '0')
                channel_runs = vid_renderer.get('ownerText', {}).get('runs', [])
                channel = ''.join(r.get('text', '') for r in channel_runs)

                # Parse duration to seconds
                dur_parts = length_text.split(':')
                dur_secs = 0
                if len(dur_parts) == 2:
                    dur_secs = int(dur_parts[0]) * 60 + int(dur_parts[1])
                elif len(dur_parts) == 3:
                    dur_secs = int(dur_parts[0]) * 3600 + int(dur_parts[1]) * 60 + int(dur_parts[2])

                # Parse views to int
                views_str = view_count_text.replace(',', '').replace(' views', '').replace(' view', '')
                try:
                    views = int(views_str)
                except ValueError:
                    views = 0

                # Thumbnail
                thumbs = vid_renderer.get('thumbnail', {}).get('thumbnails', [])
                thumb_url = thumbs[-1]['url'] if thumbs else f'https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg'

                results.append({
                    'url': f'/watch?v={vid_id}',
                    'title': title[:64],
                    'uploaderName': channel[:32],
                    'thumbnail': thumb_url,
                    'duration': dur_secs,
                    'views': views,
                    'type': 'stream',
                })

        if results:
            print(f"[Innertube Search] Found {len(results)} results")
        return results[:10]

    except Exception as e:
        print(f"[Innertube Search] Error: {e}")
        return []


def search_piped(query):
    """Fallback search via Piped API"""
    for instance in ['https://api.pipedapi.adminforge.de', 'https://pipedapi.r4fo.com']:
        try:
            url = f'{instance}/search?q={urllib.parse.quote(query)}&filter=videos'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'CardputerOS/5.0',
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
                print(f"[Piped Search] Found {len(results)} results via {instance}")
                return results
        except Exception as e:
            print(f"[Piped Search] {instance} failed: {e}")
    return []


# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/scan')
def api_scan():
    cookies_exist = os.path.exists(COOKIES_PATH)
    cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0
    return jsonify({
        'status': 'ok',
        'version': '5.0',
        'name': 'CardputerOS YouTube Server',
        'strategies': ['innertube', 'yt-dlp', 'piped', 'playwright'],
        'cookies': f'{cookies_size} bytes' if cookies_exist else 'missing',
        'sapisid': 'yes' if extractor._sapisid else 'no',
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
            'url': info.get('url', ''),
        })
    return jsonify({
        'status': 'error',
        'error': 'All extraction strategies failed.',
        'hint': 'Check Render logs for per-strategy errors.',
    })


@app.route('/streams/<video_id>')
def piped_streams(video_id):
    """Piped-compatible /streams endpoint — used by Cardputer firmware"""
    info = extractor.get_video_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404

    # Build Piped-compatible response
    return jsonify({
        'title': info.get('title', 'Unknown'),
        'description': '',
        'uploads': '',
        'uploaderUrl': '',
        'uploader': info.get('title', 'Unknown'),
        'uploaderAvatar': '',
        'thumbnailUrl': f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg',
        'uploaderName': info.get('title', 'Unknown'),
        'duration': info.get('duration', 0),
        'views': 0,
        'likes': 0,
        'dislikes': 0,
        'uploaderSubscriberCount': 0,
        'hls': '',
        'dashboards': '',
        'relatedStreams': [],
        'relatedClientStreams': [],
        'previewFrames': [],
        'audioStreams': [],
        'videoStreams': [
            {
                'url': info.get('url', ''),
                'quality': '360p',
                'format': 'MPEG_4',
                'codec': 'avc1.42001E',
                'videoOnly': False,
                'bitrate': 650000,
                'mimeType': 'video/mp4; codecs="avc1.42001E, mp4a.40.2"',
                'codecInfo': 'avc1.42001E, mp4a.40.2',
            }
        ],
    })


@app.route('/api/search')
@app.route('/search')
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'items': []})

    # Try Innertube search first (direct, reliable)
    innertube_results = search_youtube_innertube(query)
    if innertube_results:
        return jsonify({'items': innertube_results})

    # Fallback to Piped
    piped_results = search_piped(query)
    if piped_results:
        return jsonify({'items': piped_results})

    return jsonify({'items': []})


@app.route('/api/stream/<video_id>')
def api_stream(video_id):
    info = extractor.get_video_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404

    video_url = info['url']
    print(f"[Stream] Starting MJPEG for {video_id}, url_len={len(video_url)}, source={info.get('source','?')}")

    # Build cookie header for ffmpeg
    cookie_header = extractor._cookie_header if extractor._cookie_header else ''

    def generate_mjpeg():
        cmd = [
            'ffmpeg', '-re',
        ]
        if cookie_header:
            cmd += ['-headers', f'Cookie: {cookie_header}\r\nUser-Agent: Mozilla/5.0\r\n']
        else:
            cmd += ['-headers', 'User-Agent: Mozilla/5.0\r\n']
        cmd += [
            '-i', video_url,
            '-f', 'mjpeg',
            '-vf', f'scale={MJPEG_WIDTH}:{MJPEG_HEIGHT}',
            '-r', str(MJPEG_FPS), '-q:v', str(MJPEG_QUALITY),
            '-an', 'pipe:1',
        ]
        print(f"[Stream] ffmpeg cmd: {' '.join(cmd[:6])}...")
        process = None
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=65536,
            )

            # Read stderr in background thread for logging
            def log_stderr():
                try:
                    err = process.stderr.read(4096)
                    if err:
                        print(f"[Stream] ffmpeg stderr: {err.decode('utf-8', errors='replace')[:500]}")
                except Exception:
                    pass

            import threading
            t = threading.Thread(target=log_stderr, daemon=True)
            t.start()

            # Persistent buffer for JPEG frames across chunks
            buf = b''
            frame_count = 0
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk

                # Extract all complete JPEG frames from buffer
                while True:
                    soi = buf.find(b'\xff\xd8')
                    if soi < 0:
                        buf = buf[-1:] if buf.endswith(b'\xff') else b''
                        break

                    if soi > 0:
                        buf = buf[soi:]

                    eoi = buf.find(b'\xff\xd9', 2)
                    if eoi < 0:
                        break

                    frame = buf[:eoi + 2]
                    buf = buf[eoi + 2:]

                    if len(frame) > 100:
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                               + frame + b'\r\n')
                        frame_count += 1

            print(f"[Stream] Done for {video_id}, {frame_count} frames sent")

        except Exception as e:
            print(f"[Stream] MJPEG error: {e}")
        finally:
            if process:
                process.terminate()

    return Response(
        generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={'Cache-Control': 'no-cache'},
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
    print("  CardputerOS YouTube Server v5.0")
    print("=" * 50)
    cookies_exist = os.path.exists(COOKIES_PATH)
    cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0
    print(f"  Cookies: {'OK' if cookies_exist and cookies_size > 50 else 'MISSING'} ({cookies_size} bytes)")
    print(f"  SAPISID: {'YES' if extractor._sapisid else 'NO'}")
    print(f"  Strategies: Innertube -> yt-dlp -> Piped -> Playwright")
    print(f"  Port: {port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
