#!/usr/bin/env python3
"""
CardputerOS YouTube Companion Server

Transcodes YouTube videos into MJPEG streams
that the ESP32 Cardputer can decode and display.

Usage:
    pip install -r requirements.txt
    python youtube_proxy.py
"""

import os
import sys
import json
import time
import subprocess
import threading
import tempfile
import shutil
import urllib.request
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_file
import yt_dlp

# ============================================================
# Configuration
# ============================================================
SERVER_PORT = int(os.environ.get('PORT', 8080))
MJPEG_FPS = 15
MJPEG_QUALITY = 60  # JPEG quality 1-100
MJPEG_WIDTH = 240
MJPEG_HEIGHT = 135
AUDIO_SAMPLE_RATE = 22050

app = Flask(__name__)

# ============================================================
# Video Cache
# ============================================================
class VideoCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
    
    def get_stream_url(self, video_id):
        """Get direct video stream URL - try Piped API first, then yt-dlp"""
        with self._lock:
            if video_id in self._cache:
                cached = self._cache[video_id]
                if time.time() - cached.get('time', 0) < 3600:
                    return cached

        # Try Piped API instances first
        piped_instances = [
            'https://api.piped.private.coffee',
            'https://pipedapi.adminforge.de',
        ]
        
        for instance in piped_instances:
            try:
                url = f'{instance}/streams/{video_id}'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'CardputerOS/0.5',
                    'Accept': 'application/json',
                })
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read())
                    
                    if 'error' in data:
                        print(f"Piped error for {video_id}: {data['error']}")
                        continue
                    
                    # Find video stream with audio
                    video_url = None
                    for stream in data.get('videoStreams', []):
                        if not stream.get('videoOnly', True):
                            video_url = stream.get('url')
                            break
                    
                    if not video_url and data.get('videoStreams'):
                        video_url = data['videoStreams'][0].get('url')
                    
                    if video_url:
                        with self._lock:
                            self._cache[video_id] = {
                                'url': video_url,
                                'title': data.get('title', 'Unknown'),
                                'duration': data.get('duration', 0),
                                'thumbnail': data.get('thumbnailUrl', ''),
                                'time': time.time(),
                            }
                        return self._cache[video_id]
                    
            except Exception as e:
                print(f"Piped API error ({instance}): {e}")
                continue
        
        # Fallback: try yt-dlp with cookies and/or OAuth
        try:
            cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
            oauth_token = os.environ.get('OAUTH_TOKEN', '')
            
            ydl_opts = {
                'format': 'worst[ext=mp4]',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                },
            }
            if os.path.exists(cookies_path):
                ydl_opts['cookies'] = cookies_path
            
            # Write OAuth token to temp file for yt-dlp
            if oauth_token:
                oauth_path = '/tmp/yt_oauth_token'
                with open(oauth_path, 'w') as f:
                    f.write(oauth_token)
                ydl_opts['username'] = 'oauth2'
                ydl_opts['password'] = ''
                # Pass token via extractor args
                ydl_opts['extractor_args'] = {'youtube': {'oauth2_token': [oauth_path]}}
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
                
                if 'url' in info:
                    url = info['url']
                elif 'formats' in info and info['formats']:
                    formats = sorted(info['formats'], key=lambda f: f.get('height', 9999))
                    url = formats[0]['url']
                else:
                    return None
                
                with self._lock:
                    self._cache[video_id] = {
                        'url': url,
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'thumbnail': info.get('thumbnail', ''),
                        'time': time.time(),
                    }
                return self._cache[video_id]
        except Exception as e:
            print(f"yt-dlp error for {video_id}: {e}")
            return None
    
    def search(self, query):
        """Search YouTube via Piped API"""
        piped_instances = [
            'https://api.piped.private.coffee',
            'https://pipedapi.adminforge.de',
        ]
        for instance in piped_instances:
            try:
                url = f'{instance}/search?q={urllib.parse.quote(query)}&filter=videos'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'CardputerOS/0.5',
                    'Accept': 'application/json',
                })
                with urllib.request.urlopen(req, timeout=15) as response:
                    data = json.loads(response.read())
                    results = []
                    for item in data.get('items', [])[:10]:
                        vid = item.get('url', '').replace('/watch?v=', '')
                        if vid:
                            results.append({
                                'id': vid,
                                'title': item.get('title', 'Unknown')[:64],
                                'duration': f"{item.get('duration', 0) // 60}:{item.get('duration', 0) % 60:02d}",
                                'views': f"{item.get('views', 0):,}",
                            })
                    return results
            except Exception as e:
                print(f"Piped search error ({instance}): {e}")
                continue
        return []


cache = VideoCache()

# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/scan')
def api_scan():
    """Health check / server discovery"""
    return jsonify({
        'status': 'ok',
        'version': '0.1.0',
        'name': 'CardputerOS YouTube Server',
        'mjpeg_fps': MJPEG_FPS,
        'mjpeg_quality': MJPEG_QUALITY,
        'mjpeg_resolution': f'{MJPEG_WIDTH}x{MJPEG_HEIGHT}',
    })


@app.route('/api/search')
def api_search():
    """Search YouTube"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Missing query parameter q'}), 400
    
    results = cache.search(query)
    return jsonify(results)


@app.route('/api/thumb/<video_id>')
def api_thumb(video_id):
    """Get video thumbnail"""
    info = cache.get_stream_url(video_id)
    if not info:
        return 'Not found', 404
    
    # Download thumbnail
    thumb_url = info.get('thumbnail', '')
    if not thumb_url:
        return 'No thumbnail', 404
    
    try:
        req = urllib.request.Request(thumb_url)
        with urllib.request.urlopen(req) as response:
            data = response.read()
            return Response(data, mimetype='image/jpeg')
    except Exception as e:
        return f'Error: {e}', 500


@app.route('/api/stream/<video_id>', strict_slashes=False)
def api_stream(video_id):
    """MJPEG video stream - core endpoint"""
    info = cache.get_stream_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404
    
    video_url = info['url']
    
    def generate_mjpeg():
        """Generate MJPEG frames from video using ffmpeg"""
        cmd = [
            'ffmpeg',
            '-i', video_url,
            '-f', 'mjpeg',
            '-vf', f'scale={MJPEG_WIDTH}:{MJPEG_HEIGHT}',
            '-r', str(MJPEG_FPS),
            '-q:v', str(MJPEG_QUALITY),
            '-an',  # No audio for video stream
            'pipe:1'
        ]
        
        process = None
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=65536
            )
            
            # Read chunks from ffmpeg, extract complete JPEG frames
            buffer = b''
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                buffer += chunk
                
                # Extract all complete JPEG frames from buffer
                while True:
                    # Find SOI marker (FF D8)
                    soi_pos = buffer.find(b'\xff\xd8')
                    if soi_pos < 0:
                        # No SOI — keep last byte in case it's partial FF
                        buffer = buffer[-1:] if buffer.endswith(b'\xff') else b''
                        break
                    
                    # Discard anything before SOI
                    if soi_pos > 0:
                        buffer = buffer[soi_pos:]
                    
                    # Find EOI marker (FF D9) after SOI
                    eoi_pos = buffer.find(b'\xff\xd9', 2)
                    if eoi_pos < 0:
                        break  # Incomplete frame, wait for more data
                    
                    frame = buffer[:eoi_pos + 2]
                    buffer = buffer[eoi_pos + 2:]
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' +
                           frame + b'\r\n')
            
        except Exception as e:
            print(f"MJPEG error: {e}")
        finally:
            if process:
                process.terminate()
    
    return Response(
        generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
    )


@app.route('/api/audio/<video_id>')
def api_audio(video_id):
    """Audio stream - MP3 for I2S playback"""
    info = cache.get_stream_url(video_id)
    if not info:
        return jsonify({'error': 'Video not found'}), 404
    
    video_url = info['url']
    
    def generate_audio():
        """Generate MP3 audio stream"""
        cmd = [
            'ffmpeg',
            '-i', video_url,
            '-f', 'mp3',
            '-ar', str(AUDIO_SAMPLE_RATE),
            '-ac', '1',  # Mono
            '-ab', '64k',
            '-vn',  # No video
            'pipe:1'
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        
        try:
            while True:
                data = process.stdout.read(4096)
                if not data:
                    break
                yield data
        except Exception as e:
            print(f"Audio stream error: {e}")
        finally:
            process.terminate()
    
    return Response(
        generate_audio(),
        mimetype='audio/mpeg',
        headers={
            'Cache-Control': 'no-cache',
            'Transfer-Encoding': 'chunked',
        }
    )


@app.route('/api/debug/<video_id>')
def api_debug(video_id):
    """Debug endpoint - shows yt-dlp output"""
    import traceback
    try:
        cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        ydl_opts = {
            'format': 'worst[ext=mp4]',
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
        }
        if os.path.exists(cookies_path):
            ydl_opts['cookies'] = cookies_path
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)
            return jsonify({
                'status': 'ok',
                'title': info.get('title', '?'),
                'duration': info.get('duration', 0),
                'url': info.get('url', 'NONE')[:100],
                'formats_count': len(info.get('formats', [])),
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
        })


@app.route('/api/auth')
def api_auth():
    """OAuth2 device flow for yt-dlp - authorize once, works for all videos"""
    import subprocess
    import threading
    
    oauth_file = os.path.join(os.path.dirname(__file__), 'yt_dlp_token')
    
    # Check if already authorized
    if os.path.exists(oauth_file):
        return jsonify({'status': 'authenticated', 'message': 'Already authorized'})
    
    # Run yt-dlp OAuth in background, capture the URL
    def run_oauth():
        proc = subprocess.Popen(
            ['yt-dlp', '--username', 'oauth2', '--password', '', 
             '--skip-download', '--no-check-certificates',
             'https://www.youtube.com/watch?v=dQw4w9WgXcQ'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        for line in proc.stdout:
            print(f"[OAUTH] {line.strip()}")
            if 'google.com/device' in line:
                with open('/tmp/oauth_url.txt', 'w') as f:
                    f.write(line.strip())
        proc.wait()
        if proc.returncode == 0:
            with open('/tmp/oauth_done.txt', 'w') as f:
                f.write('done')
    
    # Start OAuth in background
    t = threading.Thread(target=run_oauth, daemon=True)
    t.start()
    
    # Wait up to 10 seconds for the URL to appear
    for i in range(20):
        time.sleep(0.5)
        if os.path.exists('/tmp/oauth_url.txt'):
            with open('/tmp/oauth_url.txt') as f:
                url_line = f.read()
            return jsonify({
                'status': 'needs_auth',
                'message': 'Open this URL in your browser and authorize',
                'url_line': url_line,
            })
    
    return jsonify({'status': 'waiting', 'message': 'OAuth process starting...'})


@app.route('/api/auth/status')
def api_auth_status():
    """Check if OAuth is complete"""
    oauth_file = os.path.join(os.path.dirname(__file__), 'yt_dlp_token')
    if os.path.exists(oauth_file):
        return jsonify({'status': 'authenticated'})
    if os.path.exists('/tmp/oauth_done.txt'):
        return jsonify({'status': 'just_completed'})
    return jsonify({'status': 'pending'})

@app.route('/api/play', methods=['POST'])
def api_play():
    """Start playing a video by URL"""
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'Missing url parameter'}), 400
    
    url = data['url']
    
    # Extract video ID from URL
    video_id = None
    if 'youtube.com/watch?v=' in url:
        video_id = url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        video_id = url.split('youtu.be/')[1].split('?')[0]
    else:
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    
    if not video_id:
        return jsonify({'error': 'Could not extract video ID'}), 400
    
    # Pre-cache the stream URL
    info = cache.get_stream_url(video_id)
    if not info:
        return jsonify({'error': 'Could not get video info'}), 500
    
    return jsonify({
        'status': 'playing',
        'video_id': video_id,
        'title': info.get('title', 'Unknown'),
        'duration': info.get('duration', 0),
    })


# ============================================================
# UDP Discovery (broadcast server presence)
# ============================================================

def udp_discovery_server():
    """Broadcast server presence via UDP"""
    import socket
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    message = json.dumps({
        'service': 'cardputer-youtube',
        'version': '0.1.0',
        'port': SERVER_PORT,
        'name': 'CardputerOS Server',
    }).encode()
    
    while True:
        try:
            sock.sendto(message, ('<broadcast>', 5353))
            time.sleep(2)
        except Exception:
            time.sleep(5)


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    print("=" * 50)
    print("  CardputerOS YouTube Server v0.1.0")
    print("=" * 50)
    print()
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        print("[OK] ffmpeg found")
    except FileNotFoundError:
        print("[ERROR] ffmpeg not found! Install it from https://ffmpeg.org")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] ffmpeg check failed: {e}")
        sys.exit(1)
    
    # Check yt-dlp
    try:
        import yt_dlp
        print("[OK] yt-dlp found")
    except ImportError:
        print("[ERROR] yt-dlp not found! Run: pip install yt-dlp")
        sys.exit(1)
    
    # Start UDP discovery thread
    discovery_thread = threading.Thread(target=udp_discovery_server, daemon=True)
    discovery_thread.start()
    print(f"[OK] UDP discovery started on port 5353")
    
    # Get local IP
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    
    print(f"[OK] Server starting on http://{local_ip}:{SERVER_PORT}")
    print()
    print("Set this IP in CardputerOS Settings > YouTube Server")
    print("Press Ctrl+C to stop")
    print()
    
    app.run(host='0.0.0.0', port=SERVER_PORT, threaded=True)
