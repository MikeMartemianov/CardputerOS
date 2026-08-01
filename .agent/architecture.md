# CardputerOS — Архитектура проекта

## Дерево файлов
```
CardputerOS/
├── .agent/
│   ├── ikr.md                    # ИКР документ
│   ├── tasks.md                  # Трекер задач
│   ├── architecture.md           # Этот файл
│   ├── visual_map.md             # ASCII-чертежи UI
│   ├── evolution.md              # Лог изменений
│   └── deep_analysis/
│       ├── youtube_streaming.md  # Анализ YouTube архитектуры
│       ├── memory_management.md  # Анализ памяти
│       └── keyboard_input.md     # Анализ ввода
├── platformio.ini                # Конфигурация PlatformIO
├── include/
│   ├── config.h                  # Константы проекта (размеры экрана, пины)
│   ├── os_core.h                 # Ядро ОС (scheduler, events)
│   ├── hal.h                     # Hardware Abstraction Layer
│   ├── display.h                 # Дисплей ST7789V2
│   ├── keyboard.h                # Клавиатура 56-key
│   ├── mouse.h                   # Mouse cursor system
│   ├── gui.h                     # GUI widgets
│   ├── window_manager.h          # Оконный менеджер
│   ├── taskbar.h                 # Taskbar
│   ├── app_manager.h             # Менеджер приложений
│   ├── network.h                 # WiFi + HTTP
│   ├── storage.h                 # SD + Flash
│   └── audio.h                   # I2S audio
├── src/
│   ├── main.cpp                  # Точка входа
│   ├── system/
│   │   ├── hal.cpp               # Hardware init
│   │   ├── memory.cpp            # Memory manager
│   │   ├── power.cpp             # Battery & sleep
│   │   └── ntp.cpp               # Time sync
│   ├── input/
│   │   ├── keyboard.cpp          # Matrix keyboard scan
│   │   ├── mouse.cpp             # Mouse cursor
│   │   └── events.cpp            # Event dispatcher
│   ├── gui/
│   │   ├── display.cpp           # Display driver
│   │   ├── window.cpp            # Window manager
│   │   ├── widgets.cpp           # UI widgets
│   │   ├── taskbar.cpp           # Taskbar
│   │   └── fonts.cpp             # Font management
│   ├── apps/
│   │   ├── desktop.cpp           # Desktop shell
│   │   ├── terminal.cpp          # Terminal app
│   │   ├── file_manager.cpp      # File browser
│   │   ├── youtube.cpp           # YouTube player
│   │   ├── settings.cpp          # Settings app
│   │   └── wifi_settings.cpp     # WiFi config
│   ├── network/
│   │   ├── wifi_manager.cpp      # WiFi connection
│   │   ├── http_client.cpp       # HTTP requests
│   │   ├── mjpeg_stream.cpp      # MJPEG stream decoder
│   │   └── mdns_discovery.cpp    # Server discovery
│   └── storage/
│       ├── sd_manager.cpp        # SD card access
│       └── flash_store.cpp       # Flash storage
├── server/
│   ├── youtube_proxy.py          # YouTube proxy server
│   ├── requirements.txt          # Python dependencies
│   └── README.md                 # Server setup instructions
├── resources/
│   ├── fonts/                    # Custom fonts (VLW format)
│   ├── icons/                    # App icons (RGB565 raw)
│   └── bitmaps/                  # UI elements
└── data/                         # LittleFS filesystem image
    ├── boot_logo.raw             # Boot screen
    └── default_wallpaper.raw     # Desktop wallpaper
```

## Связи между модулями
```
main.cpp
  ├── system/hal.cpp      → init all hardware
  ├── system/memory.cpp    → track heap
  ├── system/power.cpp     → battery monitor
  ├── input/keyboard.cpp   → scan keys → events
  ├── input/mouse.cpp      → cursor overlay
  ├── input/events.cpp     → dispatch to focused widget
  ├── gui/display.cpp      → LovyanGFX wrapper
  ├── gui/window.cpp       → z-order, focus management
  ├── gui/widgets.cpp      → Button, Label, TextBox
  ├── gui/taskbar.cpp      → top bar (16px)
  ├── apps/desktop.cpp     → main shell
  ├── apps/youtube.cpp     → MJPEG player
  ├── network/wifi_manager → connect to WiFi
  ├── network/mjpeg_stream → decode MJPEG frames
  └── storage/sd_manager   → file access
```

## Зависимости (PlatformIO lib_deps)
1. **M5Cardputer** — базовая библиотека (M5Unified + M5GFX + IRremote)
2. **LovyanGFX** — уже в M5GFX, высокопроизводительный graphics
3. **TJpgDec** — JPEG декодер (hardware-ускоренный на ESP32-S3)
4. **ESP32-audioI2S** — аудио декодирование (MP3, AAC, WAV)
5. **HTTPClient** — встроенная в ESP32 Arduino core
6. **LittleFS** — встроенная файловая система для Flash
