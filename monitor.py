"""CardputerOS Serial Monitor - Real-time debug"""
import serial, time, sys

ser = serial.Serial('COM3', 115200, timeout=1)

# Reset board
ser.dtr = True
time.sleep(0.05)
ser.dtr = False
time.sleep(0.1)
ser.dtr = True

print("=== CardputerOS Monitor (Ctrl+C to stop) ===")
print("Press keys on Cardputer keyboard to see debug output...\n")

try:
    while True:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            text = data.decode('utf-8', errors='replace')
            # Timestamp each line
            for line in text.split('\n'):
                line = line.rstrip()
                if line:
                    ts = time.strftime("%H:%M:%S")
                    print(f"[{ts}] {line}")
        else:
            time.sleep(0.01)
except KeyboardInterrupt:
    print("\nStopped.")
finally:
    ser.close()
