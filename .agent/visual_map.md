# CardputerOS - Visual Map

## Screen: 240x135 px (landscape)

## Desktop Layout (ASCII)
```
+--TASKBAR 16px h--240px w-----------------------+
| CardputerOS  [WiFi] [Batt] [12:34]              |
+-------------------------------------------------+
|                                                  |
|  [YT]    [Files]  [Term]   [Cfg]                 |
|  Tube                                                  |
|                                                  |
|                                                  |
|                                           [>](8x8)|
+-------------------------------------------------+
```

## YouTube Player
```
+--TITLE BAR 14px---240px-----------------------+
| [<-] YouTube Player               [-] [X]     |
+------------------------------------------------+
|                                                |
|          VIDEO AREA 240x96                     |
|          MJPEG frames here                     |
|                                                |
+------------------------------------------------+
| [<<][>][>>] ====O=== 2:34/5:12        [VOL]   |
+------------------------------------------------+
| URL: [________________________]       [Go]     |
+------------------------------------------------+
```

## Coordinate Tables

### Desktop
| Element | X  | Y  | W   | H  |
|---------|----|----|-----|----|
| Taskbar | 0  | 0  | 240 | 16 |
| Title   | 2  | 2  | 80  | 12 |
| WiFi    |170 | 2  | 12  | 12 |
| Batt    |186 | 2  | 20  | 12 |
| Clock   |210 | 2  | 28  | 12 |
| Icon YT | 20 | 40 | 40  | 48 |
| Icon Fl | 80 | 40 | 40  | 48 |
| Icon Tr |140 | 40 | 40  | 48 |
| Icon Cfg|200 | 40 | 40  | 48 |
| Cursor  |var |var | 8   | 8  |

### YouTube Player
| Element     | X   | Y   | W   | H  |
|-------------|-----|-----|-----|----|
| Title Bar   | 0   | 0   | 240 | 14 |
| Back Btn    | 2   | 2   | 10  | 10 |
| Title Text  | 14  | 2   | 190 | 10 |
| Minimize    | 214 | 2   | 10  | 10 |
| Close       | 228 | 2   | 10  | 10 |
| Video Area  | 0   | 14  | 240 | 96 |
| Controls    | 0   | 110 | 240 | 13 |
| Prev        | 2   | 112 | 10  | 10 |
| Play/Pause  | 16  | 112 | 12  | 10 |
| Next        | 32  | 112 | 10  | 10 |
| Progress    | 46  | 115 | 140 | 4  |
| Time        | 190 | 112 | 36  | 10 |
| Volume      | 228 | 112 | 10  | 10 |
| URL Bar     | 0   | 123 | 210 | 12 |
| Go Button   | 214 | 123 | 24  | 12 |

## Collision Tests
- Cursor (8x8) does not overlap taskbar when cursor Y >= 16
- YouTube controls bar (Y=110-123) does not overlap video area (Y=14-110)
- URL bar (Y=123-135) is at bottom, no overlap with controls
- All icons spaced 60px apart (40px icon + 20px gap)
