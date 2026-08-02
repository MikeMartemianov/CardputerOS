#!/usr/bin/env python3
"""Debug stream issue"""
import urllib.request, json, subprocess, time

# 1. Get fresh video URL
req = urllib.request.Request('https://cardputeros.onrender.com/api/debug/5A1fbh6dytA', headers={'User-Agent': 'test'})
resp = urllib.request.urlopen(req, timeout=30)
data = json.loads(resp.read())
resp.close()
url = data.get('url', '')
print(f'URL length: {len(url)}')
print(f'URL: {url[:200]}')

# 2. Try to access the URL directly
if url:
    req2 = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    try:
        resp2 = urllib.request.urlopen(req2, timeout=10)
        chunk = resp2.read(1024)
        print(f'Direct access: {len(chunk)} bytes')
        resp2.close()
    except Exception as e:
        print(f'Direct access FAILED: {e}')

# 3. Try ffmpeg locally
if url:
    cmd = ['ffmpeg', '-re', '-i', url, '-f', 'mjpeg', '-vf', 'scale=240:135', '-r', '15', '-q:v', '60', '-an', '-frames:v', '1', 'pipe:1']
    proc = subprocess.run(cmd, capture_output=True, timeout=15)
    print(f'ffmpeg exit code: {proc.returncode}')
    print(f'ffmpeg stdout: {len(proc.stdout)} bytes')
    stderr = proc.stderr.decode('utf-8', errors='replace')
    print(f'ffmpeg stderr: {stderr[:500]}')
