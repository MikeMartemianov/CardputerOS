# CardputerOS - Deep Analysis: Memory Management

## ESP32-S3FN8 Memory Map

### Internal SRAM (512 KB total)
```
Address Range          Size    Purpose
0x3FC80000-0x3FC9FFFF  128KB   DRAM0 (main data RAM)
0x3FFAE000-0x3FFBFFFF  128KB   DRAM1 (cacheable, WiFi use)
0x3FF80000-0x3FF8FFFF  64KB    DTCM (tightly coupled, fast)
0x3FC80000-0x3FCBFFFF  256KB   Total DRAM (contiguous)
+ RTC RAM: 16KB (for deep sleep)
```

### Memory Budget (Estimated after boot)
```
FreeRTOS kernel:           ~32 KB
WiFi stack:                ~60 KB
SPI DMA buffers:           ~16 KB
System stack:              ~16 KB
Heap metadata:             ~20 KB
-------------------------------
TOTAL SYSTEM:             ~144 KB

Available for application: ~368 KB
LCD frame buffer (1x):     ~65 KB (240x135x2 = 64,800 bytes)
JPEG decode buffer:        ~10 KB
Audio buffer:              ~8 KB
Network RX buffer:         ~16 KB
App stack (main):          ~8 KB
App stack (display):       ~8 KB
App stack (network):       ~8 KB
-------------------------------
TOTAL APP:               ~123 KB

FREE HEAP:              ~245 KB (for dynamic allocations)
```

### Flash Layout (8 MB)
```
Partition         Offset     Size     Purpose
nvs               0x9000     20KB     NVS (WiFi creds, settings)
otadata           0xE000     8KB      OTA data
app0              0x10000    3MB      Main firmware
app1              0x310000   3MB      OTA fallback
spiffs/littlefs   0x610000   1.9MB    LittleFS (fonts, icons, assets)
```

## PSRAM Status: NOT AVAILABLE
The ESP32-S3FN8 does NOT have PSRAM. All memory operations must use internal SRAM only.

## Memory Optimization Strategies

### 1. Single Frame Buffer + DMA
- Allocate ONE frame buffer (64.8KB) in SRAM
- Use SPI DMA to push to display while rendering next frame
- Double buffering NOT possible (would need 130KB)

### 2. JPEG over Raw Frames
- JPEG frame: 3-8 KB vs Raw RGB565: 64.8 KB
- Always decode JPEG directly to display buffer
- No intermediate buffer needed

### 3. Font Storage
- Small fonts (8x8, 6x8): compiled into firmware
- Medium fonts (12x16): stored in LittleFS, loaded on demand
- Large fonts (16x24): stored in LittleFS, cached in RAM

### 4. Icon/Bitmap Storage
- App icons: 32x32 RGB565 = 2048 bytes each
- Store in LittleFS as raw RGB565
- Load on demand, cache if space available

### 5. Dynamic Allocation
- Use ps_malloc/free for large allocations (NOT available without PSRAM)
- Use heap_caps_malloc with MALLOC_CAP_8BIT for DMA-capable buffers
- Monitor heap with heap_caps_get_free_size()

### 6. Task Stack Optimization
- Main task: 8KB (handles UI + app logic)
- Display task: 4KB (just pushes pixels)
- Network task: 8KB (WiFi + HTTP)
- Audio task: 4KB (I2S playback)
- Keyboard task: 2KB (matrix scanning)

## Common Memory Errors to Avoid
1. Creating String objects in loops (heap fragmentation)
2. Not freeing WiFi scan results
3. Large local arrays (>1KB) should be static or heap-allocated
4. JPEG decode buffer must be in DMA-capable memory
5. Never use new/delete in embedded - use static allocation
6. Monitor free heap periodically for leaks
