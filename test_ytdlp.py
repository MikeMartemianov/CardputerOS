#!/usr/bin/env python3
"""Test yt-dlp directly on server"""
import urllib.request, json

vid = '5A1fbh6dytA'
req = urllib.request.Request(f'https://cardputeros.onrender.com/api/ffmpeg_test/{vid}', headers={'User-Agent':'test'})
resp = urllib.request.urlopen(req, timeout=60)
data = json.loads(resp.read())
resp.close()
print(json.dumps(data, indent=2))
