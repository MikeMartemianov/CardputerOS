#!/usr/bin/env python3
import urllib.request, json

videos = ['dQw4w9WgXcQ', '5A1fbh6dytA', 'jNQXAC9IVRw', '9bZkp7q19f0']
for vid in videos:
    try:
        req = urllib.request.Request(f'https://cardputeros.onrender.com/api/debug/{vid}', headers={'User-Agent':'test'})
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        resp.close()
        src = data.get('source', '?')
        title = data.get('title', '?')[:40]
        print(f'{vid}: source={src} title={title}')
    except Exception as e:
        print(f'{vid}: ERROR {e}')
