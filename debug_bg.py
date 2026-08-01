"""
CardputerOS Debug Monitor - NO RESET, just read
"""
import serial, time, os

PORT = 'COM3'
BAUD = 115200
LOG_FILE = os.path.join(os.path.dirname(__file__), 'serial_log.txt')

def main():
    with open(LOG_FILE, 'w') as f:
        f.write(f"=== Monitor started {time.strftime('%H:%M:%S')} ===\n")

    # Open WITHOUT any DTR/RTS toggling
    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 1
    ser.dtr = False
    ser.rts = False
    ser.open()

    with open(LOG_FILE, 'a') as log:
        log.write(f"[{time.strftime('%H:%M:%S')}] Port opened (no reset)\n")
        log.flush()

    print(f"Monitoring {PORT}... Press Ctrl+C to stop")
    print("(If no output, press RESET button on Cardputer manually)\n")

    start = time.time()
    try:
        while time.time() - start < 300:  # 5 minutes
            n = ser.in_waiting
            if n > 0:
                data = ser.read(n)
                text = data.decode('utf-8', errors='replace')
                for line in text.split('\n'):
                    line = line.rstrip()
                    if line:
                        ts = time.strftime('%H:%M:%S')
                        entry = f'[{ts}] {line}'
                        print(entry)
                        with open(LOG_FILE, 'a') as log:
                            log.write(entry + '\n')
                            log.flush()
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
