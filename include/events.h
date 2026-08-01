#ifndef EVENTS_H
#define EVENTS_H
#include <Arduino.h>
#include "config.h"

#define EVT_QUEUE_SZ 32

struct OsEvent {
    uint8_t type;   // 0=none, 1=keypress, 2=keyrelease, 3=mouse_click_l, 4=mouse_click_r, 5=tick
    uint8_t key;
    int16_t mx, my;
};

void evtInit();
bool evtPush(uint8_t type, uint8_t key=0, int16_t mx=0, int16_t my=0);
bool evtPop(OsEvent* e);
uint8_t evtCount();

#endif
