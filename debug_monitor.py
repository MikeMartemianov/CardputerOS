"""CardputerOS Debug Monitor"""
import serial, time, sys

PORT = 'COM3'
BAUD = 115200

print(f"Opening {PORT} @ {BAUD}...")
ser = serial.Serial(PORT, BAUD, timeout=1)

# Close and reopen to flush
ser.close()
time.sleep(0.5)
ser.open()
time.sleep(0.3)

# Reset via DTR
ser.dtr = True
time.sleep(0.05) 
ser.dtr = False
time.sleep(0.1)
ser.dtr = True

print("Waiting for boot...")
time.sleep(4)

print("Reading serial output (15s)...\n")
start = time.time()
while time.time() - start < 15:
    try:
        n = ser.in_waiting
        if n > 0:
            data = ser.read(n)
            text = data.decode('utf-8', errors='replace')
            for line in text.split('\n'):
                line = line.rstrip()
                if line:
                    ts = time.strftime('%H:%M:%S')
                    print(f'[{ts}] {line}')
        else:
            time.sleep(0.01)
    except Exception as e:
        print(f"Error: {e}")
        break

ser.close()
print("\nDone.")
