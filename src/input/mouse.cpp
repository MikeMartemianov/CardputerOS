#include <M5Cardputer.h>
#include "../include/config.h"
#include "../include/events.h"

// Mouse cursor state
static int16_t mx=120, my=67;
static bool mvis=false, mmode=false;
static int8_t mdx=0, mdy=0;
static bool mhold=false;
static uint32_t mholdT=0, mlastT=0;
static uint16_t mbg[8*8];
static bool mbgOk=false;
static int16_t mbgx=0, mbgy=0;

static const int8_t CUR[8][8] = {
    {1,1,0,0,0,0,0,0},{1,-1,1,0,0,0,0,0},{1,-1,-1,1,0,0,0,0},{1,-1,-1,-1,1,0,0,0},
    {1,-1,-1,-1,-1,1,0,0},{1,-1,-1,-1,-1,-1,1,0},{1,-1,-1,0,0,0,0,0},{0,-1,0,0,0,0,0,0}
};

bool mouseMode() { return mmode; }
void mouseToggle() { mmode=!mmode; mvis=mmode; if(!mmode) mbgOk=false; }
int16_t mouseX() { return mx; }
int16_t mouseY() { return my; }
bool mouseVis() { return mvis; }
void mouseSetVis(bool v) { mvis=v; }
void mouseSetPos(int16_t x, int16_t y) { mx=x; my=y; mbgOk=false; }
void mouseResetDir() { mdx=0; mdy=0; mhold=false; }

bool mouseInRect(int16_t rx, int16_t ry, int16_t rw, int16_t rh) {
    return mx+4>=rx && mx+4<rx+rw && my+4>=ry && my+4<ry+rh;
}

void mouseInput(uint8_t key, bool pressed) {
    if (key==K_UP)    mdy = pressed ? -1 : 0;
    if (key==K_DOWN)  mdy = pressed ?  1 : 0;
    if (key==K_LEFT)  mdx = pressed ? -1 : 0;
    if (key==K_RIGHT) mdx = pressed ?  1 : 0;
    if (pressed && (key==K_UP||key==K_DOWN||key==K_LEFT||key==K_RIGHT)) {
        if (!mhold) { mhold=true; mholdT=millis(); }
    }
    if (!pressed && (key==K_UP||key==K_DOWN||key==K_LEFT||key==K_RIGHT)) {
        if (mdx==0 && mdy==0) mhold=false;
    }
}

void mouseClickL(bool pressed) { if(pressed) evtPush(3,0,mx,my); }
void mouseClickR(bool pressed) { if(pressed) evtPush(4,0,mx,my); }

void mouseUpdate() {
    if (!mvis) return;
    uint32_t now=millis();
    int spd = (mhold && now-mholdT>500) ? 6 : 2;
    if (now-mlastT >= 40) {
        mx += mdx*spd;
        my += mdy*spd;
        if(mx<0)mx=0; if(mx>232)mx=232;
        if(my<0)my=0; if(my>127)my=127;
        mlastT=now;
    }
}

void mouseDraw(M5GFX* d) {
    if(!mvis || !d) return;
    // erase old
    if(mbgOk) for(int py=0;py<8;py++) for(int px=0;px<8;px++)
        d->drawPixel(mbgx+px, mbgy+py, mbg[py*8+px]);
    // save bg
    for(int py=0;py<8;py++) for(int px=0;px<8;px++)
        mbg[py*8+px]=d->readPixel(mx+px,my+py);
    mbgx=mx; mbgy=my; mbgOk=true;
    // draw cursor
    for(int py=0;py<8;py++) for(int px=0;px<8;px++) {
        int8_t v=CUR[py][px];
        if(v==1) d->drawPixel(mx+px,my+py,C_WHITE);
        else if(v==-1) d->drawPixel(mx+px,my+py,C_BLACK);
    }
}
