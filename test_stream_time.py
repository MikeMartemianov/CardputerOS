import urllib.request, time

req = urllib.request.Request('https://cardputeros.onrender.com/api/stream/dQw4w9WgXcQ', headers={'User-Agent': 'CardputerOS'})
start = time.time()
resp = urllib.request.urlopen(req, timeout=30)
elapsed = time.time() - start
print(f'HTTP {resp.status} in {elapsed:.1f}s')
data = resp.read(4096)
soi = data.find(b'\xff\xd8')
eoi = data.find(b'\xff\xd9')
print(f'Bytes: {len(data)}, SOI={soi}, EOI={eoi}')
resp.close()
