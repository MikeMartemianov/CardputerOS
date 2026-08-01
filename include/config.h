#ifndef CONFIG_H
#define CONFIG_H
#include <Arduino.h>

#define SCREEN_WIDTH  240
#define SCREEN_HEIGHT 135

// Colors RGB565
#define C_BLACK    0x0000
#define C_WHITE    0xFFFF
#define C_RED      0xF800
#define C_GREEN    0x07E0
#define C_BLUE     0x001F
#define C_YELLOW   0xFFE0
#define C_CYAN     0x07FF
#define C_ORANGE   0xFD20
#define C_DGRAY    0x4208
#define C_LGRAY    0xC618
#define C_TBAR     0x1082
#define C_WINTITLE 0x001F
#define C_BTNBG    0x4208

// Pins
#define PIN_SD_CS   12
#define PIN_BATT    10
#define PIN_BKL     38

// Taskbar
#define TB_H 16

// Apps
enum AppID { APP_DESKTOP=0, APP_YOUTUBE, APP_TERMINAL, APP_SETTINGS, APP_WIFI, APP_MAX };

// Key codes mapped from M5Cardputer
enum OsKey {
    K_NONE=0, K_ESC, K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8, K_9, K_0, K_MINUS, K_EQUAL, K_BSPACE,
    K_TAB, K_Q, K_W, K_E, K_R, K_T, K_Y, K_U, K_I, K_O, K_P, K_LBR, K_RBR, K_BSLASH,
    K_CAPS, K_A, K_S, K_D, K_F, K_G, K_H, K_J, K_K, K_L, K_SCOL, K_QUOTE, K_ENTER,
    K_SHIFT, K_Z, K_X, K_C, K_V, K_B, K_N, K_M, K_COMMA, K_DOT, K_SLASH, K_UP, K_DOWN,
    K_FN, K_CTRL, K_ALT, K_SPACE, K_LEFT, K_RIGHT,
    K_F1, K_F2, K_F3, K_F4, K_F5, K_F6, K_F7, K_F8,
    K_MAX
};

#endif
