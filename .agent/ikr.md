# CardputerOS — Идеальный Конечный Результат (ИКР)

## Исходный запрос пользователя
> Я хочу сделать OS для cardputer на platform io найди всю информацию про него и как с ним работать в platform io, все ошибки которые люди совершали. Для начала я бы хотел использовать по полной его ram и psram и попробовать запустить youtube только не надо брать chromium он очень не эффективный и не оптимизированный. Всё надо оптимизировать и запустить youtube и сделать мышку что бы её стрелками можно было передвигать и нажимать enter.

---

## КРИТИЧЕСКИЙ ВЫВОД: PSRAM ОТСУТСТВУЕТ

### Анализ чипа ESP32-S3FN8
Чип M5StampS3 использует **ESP32-S3FN8** — расшифровка:
- **ESP32-S3** — серия чипа
- **F** — корпус QFN
- **N** — **БЕЗ PSRAM** (если бы была PSRAM, был бы "R" в обозначении)
- **8** — 8MB Flash

**Итого доступная память:**
| Тип | Объём | Примечание |
|-----|-------|------------|
| SRAM (internal) | 512 KB | ~320 KB доступно после FreeRTOS |
| Flash | 8 MB | Для хранения прошивки |
| PSRAM | **0 KB** | **НЕТ на ESP32-S3FN8** |

### Последствия отсутствия PSRAM
1. **Нельзя хранить кадры видео в PSRAM** — каждый кадр RGB565 240×135 = 64,800 байт
2. **Один JPEG-кадр** ~2-10 KB в зависимости от качества — помещается в SRAM
3. **Буферизация видео** сильно ограничена — максимум 1-2 кадра в буфере
4. **Шрифты и ресурсы** хранятся только во Flash ( через SPIFFS/LittleFS)

### Решение: Архитектура без PSRAM
- Используем **JPEG-декодирование кадр-за-кадром** (TJpgDec)
- Double buffering: один кадр декодируется, второй отображается
- Всё тяжёлое (шрифты, иконки) — во Flash черезLittleFS
- Видео поступает потоково с внешнего сервера (MJPEG stream)

---

## Архитектура CardputerOS

### Концепция
CardputerOS — это минималистичная операционная система для M5Stack Cardputer, предоставляющая:
1. **Desktop** с taskbar и mouse cursor
2. **Mouse cursor** — управление стрелками клавиатуры, Enter = клик
3. **YouTube Player** — подключение к companion-серверу для транскодирования YouTube → MJPEG
4. **Terminal** — базовая командная строка
5. **File Manager** — просмотр файлов на SD карте
6. **Settings** — WiFi настройки, яркость

### Экран
- **ST7789V2**: 240×135 px, 1.14", SPI
- **Orientation**: Landscape (240 горизонт, 135 вертикаль) — оптимально для видео
- **Цвета**: RGB565 (16 бит)
- **Backlight**: PWM управление через G38

### Keyboard (56 клавиш, 4×14 матрица)
- Управление через 74HC138 декодер
- Строки: G7/G6/G5/G4/G3/G15/G13 (через декодер A0/A1/A2)
- Столбцы: G11/G9/G8 (сканирование)
- Батарея ADC: G10

### Архитектура приложения
```
┌─────────────────────────────────────┐
│           CardputerOS               │
├─────────────────────────────────────┤
│  Boot → Init HAL → WiFi → Desktop  │
├─────────────────────────────────────┤
│  GUI Framework (LovyanGFX/M5GFX)  │
│  ┌──────────┬────────────────────┐  │
│  │ Taskbar  │   Active Window    │  │
│  │ (16px)   │                    │  │
│  ├──────────┤   YouTube / Term   │  │
│  │ Desktop  │   / Files / etc    │  │
│  │ Icons    │                    │  │
│  └──────────┴────────────────────┘  │
│  Mouse Cursor (drawn overlay)       │
├─────────────────────────────────────┤
│  Input Layer (Keyboard → Events)    │
├─────────────────────────────────────┤
│  Network Layer (WiFi, HTTP, MJPEG)  │
├─────────────────────────────────────┤
│  System Layer (Memory, SD, Power)   │
└─────────────────────────────────────┘
```

### YouTube — Реалистичная архитектура

**Проблема**: ESP32-S3 НЕ может декодировать H.264/H.265 в реальном времени без PSRAM и hardware decoder.

**Решение**: Companion Server Architecture
```
┌──────────────┐      HTTP/WiFi      ┌──────────────┐
│  YouTube PC  │ ──────────────────→ │  Cardputer   │
│  Server      │   MJPEG Stream      │  Display     │
│  (Python)    │   (240x135 JPEG)    │  240x135     │
│              │                     │              │
│  yt-dlp +    │                     │  TJpgDec     │
│  ffmpeg      │                     │  decoder     │
└──────────────┘                     └──────────────┘
```

**Серверная часть (Python на PC):**
1. Принимает YouTube URL от Cardputer
2. Использует `yt-dlp` для извлечения прямой ссылки на видео
3. Использует `ffmpeg` для транскодирования в MJPEG поток 240×135
4. Раздаёт MJPEG поток по HTTP на порту 8080
5. Параллельно раздаёт аудио поток (MP3/AAC) на отдельном порту

**Клиентская часть (Cardputer):**
1. Подключается к MJPEG stream URL
2. Декодирует JPEG кадры через TJpgDec (hardware-ускорение)
3. Выводит кадры на дисплей через SPI DMA
4. Параллельно воспроизводит аудио через I2S (NS4168 speaker)

### Mouse Cursor System
```
Клавиши:
  ↑ ↓ ← →   — движение курсора (ускорение при удержании)
  Enter      — левый клик (select/activate)
  Backspace  — правый клик (назад/отмена)
  Tab        — переключение между элементами
  Escape     — открытие меню/закрытие окна

Курсор:
  - размер 8x8 px (иконка стрелки)
  - рисуется как overlay поверх содержимого экрана
  - при перемещении: restore background → move → save background → draw cursor
  - cursor trail опционально для производительности
```

### Память и оптимизация
```
SRAM Layout (512 KB total):
├── FreeRTOS kernel:           ~32 KB
├── WiFi stack:                ~60 KB
├── SPI DMA buffers:           ~16 KB
├── LCD frame buffer (1 кадр): ~65 KB (240×135×2 bytes)
├── JPEG decode buffer:        ~10 KB
├── Audio buffer:              ~8 KB
├── UI state & icons:          ~20 KB
├── Network buffers:           ~32 KB
├── Stack for main task:       ~8 KB
├── Stack for WiFi task:       ~8 KB
├── Stack for display task:    ~8 KB
└── Free heap:                 ~244 KB (для приложений)
```

### Клавиатура — Маппинг клавиш
```
Стандартная раскладка Cardputer:
Row 0 (top):    ESC  1  2  3  4  5  6  7  8  9  0  -  =  BS
Row 1:          TAB  Q  W  E  R  T  Y  U  I  O  P  [  ]  \
Row 2:          CAPS  A  S  D  F  G  H  J  K  L  ;  '  ENTER
Row 3:          SHIFT  Z  X  C  V  B  N  M  ,  .  /  UP  DOWN
Row 4 (bottom): FN  CTRL  ALT  SPACE  LEFT  RIGHT  ...

Mouse mode активируется через FN+M (toggle):
- Стрелки → движение курсора
- Enter → клик
- BS → right click / back
- Остальные клавиши → передаются как текст
```

### Companion Server (Python)
```python
# youtube_proxy.py — запускается на PC в той же WiFi сети
# Зависимости: pip install yt-dlp flask

# Эндпоинты:
# GET  /api/search?q=<query>     → JSON список видео
# GET  /api/stream/<video_id>    → MJPEG stream (Content-Type: multipart/x-mixed-replace)
# GET  /api/audio/<video_id>     → Audio stream (MP3)
# GET  /api/thumbnail/<video_id> → JPEG thumbnail
# POST /api/play                 → body: {"url": "youtube.com/..."} → start streaming
```

### Компоненты приложения

1. **Boot Screen** — логотип CardputerOS, прогресс-бар, info о памяти
2. **Desktop** — фон, иконки приложений, taskbar с часами и батареей
3. **Mouse Cursor** — 8×8 px стрелка, управление стрелками
4. **YouTube App** — ввод URL, список видео, плеер с play/pause/seek
5. **Terminal** — базовые команды (ls, cat, wifi, mem, clear, help)
6. **File Manager** — просмотр SD карты
7. **Settings** — WiFi SSID/password, яркость, громкость
8. **WiFi Manager** — сканирование сетей, подключение, captive portal

### Границы и ограничения
- **Разрешение видео**: максимум 240×135 (размер экрана)
- **FPS**: ожидаемо 5-15 FPS для MJPEG на ESP32-S3 через WiFi
- **Аудио**: моно, 8-bit через NS4168 I2S speaker
- **WiFi**: только 2.4 GHz
- **Память**: без PSRAM, все буферы в SRAM
- **Батарея**: ~120 mAh + 1400 mAh base, ~1-2 часа активной работы
