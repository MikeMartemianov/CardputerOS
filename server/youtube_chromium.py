#!/usr/bin/env python3
"""
CardputerOS YouTube Server v6.0 — yt-dlp + Innertube
yt-dlp uses Node.js on Render for YouTube n-challenge solving.
"""

import hashlib
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

INNERTUBE_API_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'
INNERTUBE_SEARCH_URL = f'https://www.youtube.com/youtubei/v1/search?key={INNERTUBE_API_KEY}'


def load_netscape_cookies(path):
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
                'name': name, 'value': value, 'domain': domain,
                'path': path_val, 'secure': secure.upper() == 'TRUE',
                'expires': int(expires) if expires and expires != '0' else -1,
            })
    return cookies


def cookies_to_header(cookies, domain='.youtube.com'):
    parts = []
    for c in cookies:
        if domain in c['domain']:
            parts.append(f"{c['name']}={c['value']}")
    return '; '.join(parts)


def compute_sapisid_hash(sapisid, origin='https://www.youtube.com'):
    ts = int(time.time())
    hash_input = f"{ts} {sapisid} {origin}"
    sha1 = hashlib.sha1(hash_input.encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{sha1}"


class VideoExtractor:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
        self._cookies = load_netscape_cookies(COOKIES_PATH)
        self._cookie_header = cookies_to_header(self._cookies)
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

        # Strategy 1: yt-dlp (uses Node.js for n-challenge)
        result = self._try_ytdlp(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        # Strategy 2: Innertube API (fallback — may get 403)
        result = self._try_innertube(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        # Strategy 3: curl_cffi browser impersonation (bypasses bot detection)
        result = self._try_curl_cffi(video_id)
        if result:
            return self._cache_and_return(video_id, result)

        return None

        return None

    def _cache_and_return(self, video_id, result):
        result['time'] = time.time()
        with self._lock:
            self._cache[video_id] = result
        return result

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
            'socket_timeout': 30,
            'retries': 2,
            'extractor_args': {'youtube': {'player_client': ['tv_embedded']}},
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            },
        }
        if cookies_exist and cookies_size > 50:
            ydl_opts['cookies'] = COOKIES_PATH
            print(f"[yt-dlp] Using cookies ({cookies_size} bytes)")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False,
                )
                if 'url' in info:
                    video_url = info['url']
                elif 'formats' in info and info['formats']:
                    formats = sorted(info['formats'], key=lambda f: f.get('height', 9999))
                    video_url = formats[0]['url']
                else:
                    return None
                print(f"[yt-dlp] Success for {video_id}")
                return {
                    'url': video_url,
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'source': 'yt-dlp',
                }
        except Exception as e:
            print(f"[yt-dlp] Error: {e}")
            return None

    def _try_innertube(self, video_id):
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Origin': 'https://www.youtube.com',
            }
            if self._sapisid and self._cookie_header:
                headers['Authorization'] = compute_sapisid_hash(self._sapisid)
                headers['Cookie'] = self._cookie_header
            elif self._cookie_header:
                headers['Cookie'] = self._cookie_header

            payload = {
                'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20250101.00.00'}},
                'videoId': video_id,
            }
            api_key = INNERTUBE_API_KEY
            player_url = f'https://www.youtube.com/youtubei/v1/player?key={api_key}'

            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(player_url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())

            streaming = body.get('streamingData', {})
            formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])

            # Try combined formats first (have audio+video), then any video, then any URL
            video_url = None
            for fmt in formats:
                if fmt.get('mimeType', '').startswith('video/') and 'url' in fmt and fmt.get('audioQuality'):
                    video_url = fmt['url']
                    break
            if not video_url:
                for fmt in formats:
                    if fmt.get('mimeType', '').startswith('video/') and 'url' in fmt:
                        video_url = fmt['url']
                        break
            if not video_url:
                for fmt in formats:
                    if 'url' in fmt:
                        video_url = fmt['url']
                        break

            title = body.get('videoDetails', {}).get('title', 'Unknown')
            duration = int(body.get('videoDetails', {}).get('lengthSeconds', 0))

            if video_url:
                print(f"[Innertube] Success for {video_id}")
                return {'url': video_url, 'title': title, 'duration': duration, 'source': 'innertube'}

        except Exception as e:
            print(f"[Innertube] Error: {e}")
        return None

    def _try_curl_cffi(self, video_id):
        """Browser impersonation via curl_cffi — mimics Chrome TLS fingerprint.
        YouTube bot detection checks TLS ClientHello; curl_cffi impersonates
        a real browser, bypassing 'Sign in to confirm you're not a bot'.
        Lightweight: no Chromium, no CPU-heavy rendering."""
        try:
            from curl_cffi import requests as cffi_requests
        except Exception as e:
            print(f"[curl_cffi] Import failed: {e}")
            return None

        # Try multiple mobile clients — these work without cookies/PO tokens
        clients = [
            {'clientName': 'ANDROID', 'clientVersion': '20.10.33',
             'androidSdkVersion': 33, 'osName': 'Android', 'osVersion': '14'},
            {'clientName': 'ANDROID', 'clientVersion': '21.02.34',
             'androidSdkVersion': 35, 'osName': 'Android', 'osVersion': '15'},
            {'clientName': 'IOS', 'clientVersion': '20.10.4',
             'deviceMake': 'Apple', 'deviceModel': 'iPhone17,2',
             'osName': 'iPhone', 'osVersion': '18.3.1'},
        ]

        for client_ctx in clients:
            try:
                payload = {
                    'context': {'client': client_ctx},
                    'videoId': video_id,
                }
                is_android = client_ctx.get('clientName') == 'ANDROID'
                headers = {'Origin': 'https://www.youtube.com'}
                if is_android:
                    headers['User-Agent'] = (
                        'com.google.android.youtube/20.10.33 (Linux; U; Android 14) gzip')

                resp = cffi_requests.post(
                    INNERTUBE_SEARCH_URL.replace('/search?', '/player?'),
                    json=payload,
                    impersonate='chrome',
                    headers=headers,
                    timeout=20,
                )
                if resp.status_code != 200:
                    print(f"[curl_cffi] HTTP {resp.status_code}")
                    continue

                body = resp.json()
                streaming = body.get('streamingData', {})
                formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])

                video_url = None
                for fmt in formats:
                    if fmt.get('mimeType', '').startswith('video/') and 'url' in fmt:
                        if fmt.get('audioQuality'):
                            video_url = fmt['url']
                            break
                if not video_url:
                    for fmt in formats:
                        if 'url' in fmt:
                            video_url = fmt['url']
                            break

                title = body.get('videoDetails', {}).get('title', 'Unknown')
                duration = int(body.get('videoDetails', {}).get('lengthSeconds', 0))

                if video_url:
                    client_name = client_ctx.get('clientName', '?')
                    print(f"[curl_cffi] Success for {video_id} via {client_name}")
                    return {'url': video_url, 'title': title, 'duration': duration,
                            'source': f'curl-{client_name.lower()}'}

            except Exception as e:
                print(f"[curl_cffi] {client_ctx.get('clientName')} failed: {e}")
                continue

        return None


extractor = VideoExtractor()


def search_youtube_innertube(query):
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
        'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20240801.00.00'}},
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

                dur_parts = length_text.split(':')
                dur_secs = 0
                if len(dur_parts) == 2:
                    dur_secs = int(dur_parts[0]) * 60 + int(dur_parts[1])
                elif len(dur_parts) == 3:
                    dur_secs = int(dur_parts[0]) * 3600 + int(dur_parts[1]) * 60 + int(dur_parts[2])

                views_str = view_count_text.replace(',', '').replace(' views', '').replace(' view', '')
                try:
                    views = int(views_str)
                except ValueError:
                    views = 0

                results.append({
                    'url': f'/watch?v={vid_id}',
                    'title': title[:64],
                    'uploaderName': channel[:32],
                    'thumbnail': f'https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg',
                    'duration': dur_secs,
                    'views': views,
                    'type': 'stream',
                })
        return results[:10]
    except Exception as e:
        print(f"[Innertube Search] Error: {e}")
        return []


# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/scan')
def api_scan():
    cookies_exist = os.path.exists(COOKIES_PATH)
    cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0
    
    # Check yt-dlp + Node.js availability
    ytdlp_ok = False
    node_ok = False
    ytdlp_ver = ''
    node_ver = ''
    ejs_ok = False
    try:
        import yt_dlp
        ytdlp_ver = yt_dlp.version.__version__
        ytdlp_ok = True
    except Exception as e:
        ytdlp_ver = str(e)
    try:
        r = subprocess.run(['node', '--version'], capture_output=True, timeout=5, text=True)
        node_ver = r.stdout.strip()
        node_ok = r.returncode == 0
    except Exception as e:
        node_ver = str(e)
    try:
        import yt_dlp_ejs
        ejs_ok = True
    except ImportError:
        pass
    
    return jsonify({
        'status': 'ok',
        'version': '6.0',
        'name': 'CardputerOS YouTube Server',
        'strategies': ['yt-dlp', 'innertube'],
        'cookies': f'{cookies_size} bytes' if cookies_exist else 'missing',
        'sapisid': 'yes' if extractor._sapisid else 'no',
        'ytdlp': f'{ytdlp_ver} ok={ytdlp_ok}',
        'node': f'{node_ver} ok={node_ok}',
        'ejs': ejs_ok,
        'mjpeg_fps': MJPEG_FPS,
    })


@app.route('/api/debug/<video_id>')
@app.route('/streams/<video_id>')
def api_debug(video_id):
    try:
        info = extractor.get_video_url(video_id)
    except Exception as e:
        print(f"[Debug] Extraction error: {e}")
        info = None
    if info:
        # For /streams/ route, return Piped-compatible format
        if request.path.startswith('/streams/'):
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'description': '',
                'duration': info.get('duration', 0),
                'views': 0,
                'thumbnailUrl': f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg',
                'uploaderName': info.get('title', 'Unknown'),
                'videoStreams': [{
                    'url': info.get('url', ''),
                    'quality': '360p',
                    'format': 'MPEG_4',
                    'videoOnly': False,
                    'mimeType': 'video/mp4',
                }],
                'audioStreams': [],
                'previewFrames': [],
            })
        return jsonify({
            'status': 'ok',
            'source': info.get('source', '?'),
            'title': info.get('title', '?'),
            'duration': info.get('duration', 0),
            'url': info.get('url', ''),
        })
    return jsonify({'status': 'error', 'error': 'All extraction strategies failed.'})


@app.route('/api/search')
@app.route('/search')
def api_search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'items': []})
    results = search_youtube_innertube(query)
    return jsonify({'items': results}) if results else jsonify({'items': []})


@app.route('/api/stream/<video_id>')
def api_stream(video_id):
    # Accept pre-extracted URL from ESP32 (avoids YouTube bot detection on server IP)
    pre_url = request.args.get('url', '')
    cookie_header = extractor._cookie_header if extractor._cookie_header else ''

    def generate_mjpeg():
        if pre_url:
            # ESP32 extracted the URL via Innertube API (home IP, not blocked)
            video_url = pre_url
            source = 'esp32-innertube'
            print(f"[Stream] MJPEG for {video_id}, source={source} (ESP32-provided URL)")
        else:
            # Server-side extraction (may fail on Render due to IP blocking)
            try:
                info = extractor.get_video_url(video_id)
            except Exception as e:
                print(f"[Stream] Extraction error: {e}")
                info = None
            if not info:
                print(f"[Stream] No URL for {video_id}")
                return
            video_url = info.get('url', '')
            source = info.get('source', '?')
            if not video_url:
                print(f"[Stream] Empty URL for {video_id}")
                return
            print(f"[Stream] MJPEG for {video_id}, source={source}, url_len={len(video_url)}")

        cmd = ['ffmpeg', '-re']
        headers_str = 'User-Agent: Mozilla/5.0\r\nReferer: https://www.youtube.com/\r\n'
        if cookie_header:
            headers_str += f'Cookie: {cookie_header}\r\n'
        cmd += ['-headers', headers_str]
        cmd += ['-i', video_url, '-f', 'mjpeg', '-vf', f'scale={MJPEG_WIDTH}:{MJPEG_HEIGHT}',
                '-r', str(MJPEG_FPS), '-q:v', str(MJPEG_QUALITY), '-an', 'pipe:1']

        process = None
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=65536)

            def log_stderr():
                try:
                    err = process.stderr.read(4096)
                    if err:
                        print(f"[Stream] ffmpeg stderr: {err.decode('utf-8', errors='replace')[:500]}")
                except Exception:
                    pass

            t = threading.Thread(target=log_stderr, daemon=True)
            t.start()

            buf = b''
            frame_count = 0
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk
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
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                        frame_count += 1

            print(f"[Stream] Done for {video_id}, {frame_count} frames")
        except Exception as e:
            print(f"[Stream] Error: {e}")
        finally:
            if process:
                process.terminate()

    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame',
                    headers={'Cache-Control': 'no-cache'})


@app.route('/api/audio/<video_id>')
def api_audio(video_id):
    info = extractor.get_video_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404
    video_url = info['url']

    def generate_audio():
        cmd = ['ffmpeg', '-i', video_url, '-f', 'mp3', '-ar', str(AUDIO_SAMPLE_RATE),
               '-ac', '1', '-ab', '64k', '-vn', 'pipe:1']
        process = None
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            while True:
                data = process.stdout.read(4096)
                if not data:
                    break
                yield data
        except Exception as e:
            print(f"Audio error: {e}")
        finally:
            if process:
                process.terminate()

    return Response(generate_audio(), mimetype='audio/mpeg',
                    headers={'Cache-Control': 'no-cache', 'Transfer-Encoding': 'chunked'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 50)
    print("  CardputerOS YouTube Server v6.0")
    print("=" * 50)
    cookies_exist = os.path.exists(COOKIES_PATH)
    cookies_size = os.path.getsize(COOKIES_PATH) if cookies_exist else 0
    print(f"  Cookies: {'OK' if cookies_exist and cookies_size > 50 else 'MISSING'} ({cookies_size} bytes)")
    print(f"  SAPISID: {'YES' if extractor._sapisid else 'NO'}")
    print(f"  Strategies: yt-dlp -> Innertube")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False)
