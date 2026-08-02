import serial, time
ser = serial.Serial('COM3', 115200, timeout=1)
ser.dtr = False; time.sleep(0.05); ser.dtr = True; time.sleep(0.05); ser.dtr = False
time.sleep(3)
ser.reset_input_buffer()
print('=== Monitor 90s ===')
start = time.time()
while time.time() - start < 90:
    if ser.in_waiting:
        data = ser.read(ser.in_waiting)
        text = data.decode('utf-8', errors='replace')
        for line in text.split('\n'):
            if line.strip():
                ts = time.strftime('%H:%M:%S')
                print(f'[{ts}] {line.rstrip()}', flush=True)
    else:
        time.sleep(0.01)
ser.close()
