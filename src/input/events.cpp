#include <Arduino.h>
#include "../include/config.h"
#include "../include/events.h"

static OsEvent q[EVT_QUEUE_SZ];
static uint8_t head=0, tail=0, cnt=0;

void evtInit() { head=tail=cnt=0; }

bool evtPush(uint8_t type, uint8_t key, int16_t mx, int16_t my) {
    if (cnt >= EVT_QUEUE_SZ) { head = (head+1)%EVT_QUEUE_SZ; cnt--; }
    q[tail] = {type, key, mx, my};
    tail = (tail+1)%EVT_QUEUE_SZ;
    cnt++;
    return true;
}

bool evtPop(OsEvent* e) {
    if (!cnt) return false;
    *e = q[head];
    head = (head+1)%EVT_QUEUE_SZ;
    cnt--;
    return true;
}

uint8_t evtCount() { return cnt; }
