import sqlite3
import os
import shutil
import tempfile

# Chrome cookie database path
chrome_path = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies')

# Copy to temp to avoid lock
tmp = tempfile.mktemp(suffix='.db')
shutil.copy2(chrome_path, tmp)

conn = sqlite3.connect(tmp)
cursor = conn.cursor()

# Get YouTube cookies
cursor.execute("""
    SELECT host_key, path, is_secure, expires_utc, name, value, encrypted_value
    FROM cookies 
    WHERE host_key LIKE '%youtube%' OR host_key LIKE '%google%'
    ORDER BY name
""")

output = "# Netscape HTTP Cookie File\n"
count = 0
for row in cursor.fetchall():
    host, path, secure, expires, name, value, enc_value = row
    # If value is empty but encrypted_value exists, use encrypted
    if not value and enc_value:
        value = f"encrypted_{len(enc_value)}_bytes"
    secure_str = "TRUE" if secure else "FALSE"
    # Chrome epoch: microseconds since 1601-01-01
    # Convert to Unix timestamp
    if expires > 0:
        unix_exp = int((expires - 11644473600000000) / 1000000)
    else:
        unix_exp = 0
    output += f"{host}\tTRUE\t{path}\t{secure_str}\t{unix_exp}\t{name}\t{value}\n"
    count += 1

conn.close()
os.unlink(tmp)

print(f"Found {count} YouTube/Google cookies")
with open('E:/mikem/CardputerOS/server/cookies.txt', 'w') as f:
    f.write(output)
print("Saved to cookies.txt")
