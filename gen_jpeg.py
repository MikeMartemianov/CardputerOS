from PIL import Image
import io

img = Image.new('RGB', (240, 135), (0, 0, 0))
buf = io.BytesIO()
img.save(buf, 'JPEG', quality=30)
data = buf.getvalue()

with open('E:/mikem/CardputerOS/server/black_frame.jpg', 'wb') as f:
    f.write(data)

print(f'Saved black_frame.jpg ({len(data)} bytes)')
