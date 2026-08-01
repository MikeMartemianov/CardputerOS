# Common Errors People Made with M5Stack Cardputer + PlatformIO

## 1. Wrong Board Definition
**Error**: Using `board = m5stack-stamps3` or wrong board name
**Fix**: Use `board = esp32-s3-devkitc-1` - M5Stack doesn't have official PlatformIO board defs for Cardputer
```ini
; CORRECT
board = esp32-s3-devkitc-1

; WRONG
board = m5stack-cardputer  ; Does not exist in PlatformIO
```

## 2. Missing USB CDC Build Flags
**Error**: Serial Monitor shows nothing, upload fails
**Fix**: Add USB CDC flags
```ini
build_flags =
    -DARDUINO_USB_CDC_ON_BOOT=1
    -DARDUINO_USB_MODE=1
```

## 3. Wrong Library Dependency
**Error**: `M5Stack.h` not found or wrong include
**Fix**: Use M5Cardputer library (not M5Stack or M5Core2)
```ini
lib_deps =
    M5Cardputer=https://github.com/m5stack/M5Cardputer
```
```cpp
// CORRECT
#include <M5Cardputer.h>

// WRONG
#include <M5Stack.h>      // Old library for M5Stack Basic/Gray
#include <M5Core2.h>       // For Core2, not Cardputer
```

## 4. PSRAM Enabled When Not Available
**Error**: Build fails or crash at runtime with `psram` related errors
**Fix**: ESP32-S3FN8 does NOT have PSRAM. Do NOT enable PSRAM flags:
```ini
; WRONG - will crash
board_build.arduino.memory_type = qio_opi  ; This enables PSRAM

; CORRECT - no PSRAM type specified
; Just omit memory_type entirely
```

## 5. Wrong Upload Speed
**Error**: Upload fails or corrupts
**Fix**: Use correct baud rate
```ini
upload_speed = 1500000  ; 1.5 Mbps for USB CDC
```

## 6. Forgetting Platform Version
**Error**: Library compatibility issues
**Fix**: Pin the espressif32 platform version
```ini
platform = espressif32@6.7.0  ; Tested version
```

## 7. Display Not Working
**Error**: Black screen or garbled display
**Fix**: M5Cardputer initializes display internally. Don't re-init:
```cpp
// CORRECT - M5Cardputer handles display init
auto cfg = M5Cardputer.config;
cfg.clear_display = false;
M5Cardputer.begin(cfg);

// WRONG - trying to init display separately
tft.init();  // Conflicts with M5Cardputer
```

## 8. Keyboard Not Reading
**Error: Keyboard always returns no key
**Fix**: M5Cardputer handles keyboard scanning internally:
```cpp
// CORRECT
M5Cardputer.Keyboard.update();
if (M5Cardputer.Keyboard.isPressed()) {
    // Check specific keys
}

// WRONG - trying direct GPIO scan
digitalRead(KB_PIN);  // Keyboard uses matrix + decoder, not direct GPIO
```

## 9. SD Card Not Mounting
**Error**: SD.begin() fails
**Fix**: Use correct CS pin (G12 on Cardputer):
```cpp
SD.begin(12);  // CS = G12
```

## 10. Speaker/Microphone Not Working
**Error**: No audio input/output
**Fix**: I2S pins for Cardputer:
```cpp
// Speaker (NS4168): BCLK=41, SDATA=42, LRCLK=43
// Microphone (SPM1423): DAT=46, CLK=43
// Note: Speaker and Mic share LRCLK/CLK pin (G43)!
```

## 11. Partition Table Error
**Error**: Firmware too large for default partition
**Fix**: Use 8MB partition table
```ini
board_build.partitions = default_8MB.csv
board_build.flash_size = 8MB
```

## 12. Memory Overflow (No PSRAM)
**Error**: `lwip` or `malloc` fails, system crashes
**Fix**: Monitor heap, don't allocate large buffers:
```cpp
Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
// Don't allocate more than 200KB dynamically
// Single frame buffer: 240*135*2 = 64,800 bytes max
```

## 13. WiFi Disconnects During Stream
**Error**: MJPEG stream drops after few seconds
**Fix**: Implement reconnect logic and larger TCP buffers:
```cpp
WiFi.setAutoReconnect(true);
WiFi.persistent(true);
```

## 14. GPIO Conflicts
**Error**: Multiple peripherals on same GPIO
**Fix**: Cardputer GPIO map:
```
G38: Display backlight
G33-G37: Display SPI (RST, RS, DAT, SCK, CS)
G46: Microphone DAT
G43: Speaker LRCLK + Mic CLK (shared!)
G41-G42: Speaker I2S (BCLK, SDATA)
G44: IR TX
G12,G14,G40,G39: SD Card SPI
G10: Battery ADC
G7/G6/G5/G4/G3/G15/G13: Keyboard rows
G11/G9/G8: Keyboard columns
G1-G2: HY2.0 I2C
```

## 15. Download Mode Confusion
**Error**: Can't upload firmware
**Fix**: To enter download mode on Cardputer:
1. Switch power to OFF
2. Hold G0 button
3. Power ON
4. Release G0
Then upload.
