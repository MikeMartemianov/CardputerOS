#ifndef MOUSE_H
#define MOUSE_H

#include <Arduino.h>
#include "config.h"

// ============================================================
// Mouse Cursor System for CardputerOS
// Controlled by keyboard arrows + Enter/Backspace
// C-style API (matches mouse.cpp implementation)
// ============================================================

// Mouse mode state
bool mouseMode();
void mouseToggle();

// Position getters/setters
int16_t mouseX();
int16_t mouseY();
bool mouseVis();
void mouseSetVis(bool visible);
void mouseSetPos(int16_t x, int16_t y);

// Input handling
void mouseInput(uint8_t key, bool pressed);  // Arrow keys
void mouseClickL(bool pressed);              // Left click (Enter)
void mouseClickR(bool pressed);              // Right click (Backspace)
void mouseResetDir();                        // Reset movement direction

// Hit testing
bool mouseInRect(int16_t rx, int16_t ry, int16_t rw, int16_t rh);

// Update & draw (call every frame)
void mouseUpdate();
void mouseDraw(M5GFX* display);

#endif  // MOUSE_H