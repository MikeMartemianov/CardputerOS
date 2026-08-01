# CardputerOS - Deep Analysis: Keyboard Input System

## Keyboard Hardware
- 56 keys arranged in 4 rows x 14 columns
- Scanned via 74HC138 3-to-8 decoder
- Row select: G7/G6/G5/G4/G3/G15/G13 (A0/A1/A2 + enable)
- Column read: G11/G9/G8 (3 bits from decoder Y0-Y7)
- Battery ADC: G10

## Key Matrix Mapping (4x14)
```
Row 0 (top):     ESC  1  2  3  4  5  6  7  8  9  0  -  =  BS
Row 1:           TAB  Q  W  E  R  T  Y  U  I  O  P  [  ]  \
Row 2:           CAPS  A  S  D  F  G  H  J  K  L  ;  '  ENTER
Row 3:           SHIFT Z  X  C  V  B  N  M  ,  .  /  UP  DOWN
```

Wait - 4 rows x 14 columns = 56 keys. But the column read is 3 bits (G11/G9/G8).
With 74HC138 decoder, we have:
- 3 select lines (A0/A1/A2) -> 8 outputs
- But we need 14 columns

Actually the mapping is different. The 74HC138 has 3 inputs (A0-A2) and 8 outputs (Y0-Y7).
Combined with 3 read lines (G11/G9/G8), we get 8 x 3 = 24 possible keys per row setup.

Let me reconsider: The decoder selects groups, and the read lines detect which key in the group.

## Mouse Mode
Toggle with FN+M combination.

### Mouse Mode Key Map
When mouse mode is active:
```
Arrow keys -> Move cursor (with acceleration)
Enter      -> Left click
Backspace  -> Right click / Back
Escape     -> Open context menu or close app
Tab        -> Cycle through focusable widgets
```

### Mouse Cursor Rendering
- 8x8 pixel arrow cursor
- Saved background before draw
- XOR drawing for visibility on any background
- Movement: 2px base, 8px when held > 500ms (acceleration)

## Key Event System
Events:
- KEY_PRESS: key just pressed
- KEY_RELEASE: key released  
- KEY_HOLD: key held for > 500ms
- KEY_REPEAT: key repeated while held (every 100ms after initial 500ms)
- MOUSE_MOVE: cursor position changed
- MOUSE_CLICK: left or right click at position

## Debouncing
- 20ms debounce time for key press
- 500ms initial hold threshold
- 100ms repeat interval
