# CardputerOS — Трекер задач

## Фаза 1: Инфраструктура проекта
- [x] Создать структуру каталогов
- [ ] Настроить platformio.ini с правильными параметрами
- [ ] Настроить раздел LittleFS для шрифтов/иконок
- [ ] Создать базовый HAL (Hardware Abstraction Layer)

## Фаза 2: System Layer
- [ ] Инициализация дисплея ST7789V2 через LovyanGFX
- [ ] Инициализация клавиатуры (56-key matrix scan)
- [ ] Менеджер памяти (heap tracking, PSRAM check)
- [ ] PWM backlight control
- [ ] Battery monitor (ADC G10)
- [ ] I2S Speaker init (NS4168)
- [ ] I2S Microphone init (SPM1423)
- [ ] SD Card reader init
- [ ] WiFi manager (scan, connect, reconnect)
- [ ] NTP time sync

## Фаза 3: Input Layer
- [ ] Keyboard scanner (4×14 matrix via 74HC138)
- [ ] Key event system (press, release, hold, repeat)
- [ ] Mouse cursor mode toggle (FN+M)
- [ ] Mouse cursor rendering (8×8 overlay)
- [ ] Mouse movement with acceleration
- [ ] Click event dispatching

## Фаза 4: GUI Framework
- [ ] Window manager (z-order, focus, close)
- [ ] Taskbar (clock, battery, active apps)
- [ ] Desktop with app icons
- [ ] Button/Label/TextBox widgets
- [ ] Dialog boxes (alert, confirm, input)
- [ ] Scroll support for lists
- [ ] Animation system (transitions)

## Фаза 5: Apps
- [ ] Terminal (basic commands, scrollback)
- [ ] File Manager (SD card browsing)
- [ ] WiFi Settings (scan, connect, save)
- [ ] YouTube Player (MJPEG stream, controls)
- [ ] Settings (brightness, volume, about)
- [ ] Memory Monitor (heap, tasks)

## Фаза 6: Companion Server
- [ ] Python YouTube proxy server
- [ ] yt-dlp integration for stream extraction
- [ ] ffmpeg MJPEG transcoding pipeline
- [ ] HTTP API endpoints
- [ ] Audio streaming
- [ ] Auto-discovery (mDNS/UDP broadcast)

## Фаза 7: Testing & Optimization
- [ ] Memory leak testing
- [ ] FPS benchmarking
- [ ] WiFi reconnection resilience
- [ ] Keyboard debouncing
- [ ] Power management
- [ ] OTA update support
