#!/usr/bin/env python3
import urllib.request, json

# Test stream for previously failing video
vid = '5A1fbh6dytA'
req = urllib.request.Request(f'https://cardputeros.onrender.com/api/stream/{vid}', headers={'User-Agent':'CardputerOS'})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    data = resp.read(8192)
    print(f'Got {len(data)} bytes')
    soi = data.find(b'\xff\xd8')
    eoi = data.find(b'\xff\xd9')
    print(f'SOI={soi} EOI={eoi}')
    if soi >= 0 and eoi >= 0:
        print(f'First JPEG: {eoi - soi + 2} bytes - WORKS!')
    resp.close()
except Exception as e:
    print(f'ERROR: {e}')
