// ============================================================
// CardputerOS v0.6 — YouTube via Companion Server (MJPEG+Audio)
// ============================================================
#include <M5Cardputer.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include "config.h"
#include "events.h"

extern bool mouseMode();extern void mouseToggle();
extern int16_t mouseX();extern int16_t mouseY();
extern bool mouseVis();extern void mouseSetVis(bool);
extern void mouseSetPos(int16_t,int16_t);
extern bool mouseInRect(int16_t,int16_t,int16_t,int16_t);
extern void mouseInput(uint8_t,bool);
extern void mouseResetDir();
extern void mouseClickL(bool);extern void mouseClickR(bool);
extern void mouseUpdate();extern void mouseDraw(M5GFX*);

static Preferences prefs;
static AppID currentApp = APP_DESKTOP;
static char wifiSSID[33]="", wifiPass[65]="";
static bool wifiConnected=false;
static char termInput[128]="";static uint8_t termInputLen=0;
static char termLines[12][80];static uint8_t termLineCount=0;
static int8_t settingsRow=0, brightness=255;

// YouTube Cloudflare Worker proxy — set your worker URL here
static char ytWorkerUrl[128]=""; // Set Cloudflare Worker URL here if deployed
// Companion server for video streaming  
static char ytServerIP[64]="cardputeros.onrender.com";
// Storyboard "video" player
struct YtStoryboard{char url[200];int frameW;int frameH;int total;int durPerFrame;int perRow;int perCol;};
static YtStoryboard ytSb={};static int ytSbCurFrame=0;static uint32_t ytSbLastFrame=0;
static uint8_t* ytSbSheetBuf=nullptr;static size_t ytSbSheetSize=0;
static uint8_t* ytSbFrameBuf=nullptr;
static char ytQuery[128]="";static uint8_t ytQueryLen=0;
static bool ytQueryMode=true; // true=search input, false=results/player
// Search results
struct YtResult{char id[12];char title[64];char channel[32];char thumb[200];int duration;int views;};
static YtResult ytResults[10];static int ytResultCount=0;static int8_t ytResultSel=0;
// Player state
static enum{YT_IDLE,YT_LOADING,YT_PLAYING} ytPlayerState=YT_IDLE;
static char ytPlayTitle[64]="";static char ytPlayChannel[32]="";
static int ytPlayDuration=0;static int ytPlayViews=0;
static char ytPlayThumbUrl[200]="";static char ytPlayVideoUrl[500]="";
static uint8_t* ytThumbBuf=nullptr;static size_t ytThumbSize=0;
static bool ytLoadingThumb=false;
// MJPEG streaming from companion server
static bool ytStreaming=false;static WiFiClientSecure ytStreamClient;static HTTPClient ytHttp;
static bool ytInFrame=false;static size_t ytFrameDataPos=0;
static uint8_t ytFrameData[240*135*2];

static int wifiScanCount=0;static String wifiScanNames[20];
static bool wifiScanEncrypted[20];
static int8_t wifiScanSel=0;static bool wifiScanning=false;
static bool wifiInputMode=false;static char wifiInputBuf[65]="";static uint8_t wifiInputLen=0;
static int8_t wifiStatus=0; // 0=typing, 1=connecting, 2=success, 3=fail
static bool fnHeld=false, shiftHeld=false, ctrlHeld=false;

// Key repeat state
static uint32_t keyRepeatStart = 0;
static uint32_t keyRepeatLast = 0;
static OsKey lastKey = K_NONE;
static char lastChar = 0;
static bool keyHeld = false;
static uint32_t keyDebounceTime = 0;  // Cooldown after release to prevent bounce
static OsKey prevFrameKey = K_NONE;   // Key from previous scan frame (debounce core)

// Forward declarations for YouTube
static void ytSearch();
static void ytLoadVideo(const char* videoId);
static void ytFreeThumb();
static void drawYouTube();

// ============================================================
// DRAW
// ============================================================
static void dRect(int x,int y,int w,int h,uint16_t c){M5Cardputer.Display.drawRect(x,y,w,h,c);}
static void fRect(int x,int y,int w,int h,uint16_t c){M5Cardputer.Display.fillRect(x,y,w,h,c);}
static void dTxt(int x,int y,const char* t,uint16_t c,uint8_t sz=1){
    M5Cardputer.Display.setTextSize(sz);M5Cardputer.Display.setTextColor(c);
    M5Cardputer.Display.setCursor(x,y);M5Cardputer.Display.print(t);}
static void clear(uint16_t c=C_BLACK){M5Cardputer.Display.fillScreen(c);}

// ============================================================
// KEYBOARD — M5Cardputer Keyboard (IOMatrix via 74HC138)
// ============================================================

// Also try M5Cardputer's keyboard
static void kbM5Scan() {
    M5Cardputer.update();
}

// ============================================================
// TASKBAR
// ============================================================
static void drawTaskbar(){
    fRect(0,0,240,TB_H,C_TBAR);
    dTxt(2,2,"CardputerOS",C_WHITE);
    dTxt(140,2,wifiConnected?"WiFi":"---",wifiConnected?C_GREEN:C_RED);
    int raw=analogRead(PIN_BATT);float vbat=(raw/4095.0f)*3.3f*2.0f;
    int pct=vbat>=4.2f?100:(vbat<=3.0f?0:(int)((vbat-3.0f)/12.0f));
    char bstr[8];snprintf(bstr,8,"%d%%",pct);dTxt(200,2,bstr,C_WHITE);
    const char* names[]={"Desktop","YouTube","Terminal","Settings","WiFi"};
    dTxt(80,2,names[currentApp],C_LGRAY);
    if(mouseMode())dTxt(228,2,"M",C_CYAN);
}

// ============================================================
// DESKTOP
// ============================================================
struct Icon{const char*name;int x,y;uint16_t color;AppID app;};
static Icon icons[]={
    {"YouTube",15,30,C_RED,APP_YOUTUBE},{"Terminal",65,30,C_GREEN,APP_TERMINAL},
    {"Settings",115,30,C_BLUE,APP_SETTINGS},{"WiFi",165,30,C_YELLOW,APP_WIFI},
    {"Info",215,30,C_CYAN,APP_DESKTOP},
};
static const int ICON_COUNT=5;

static void drawDesktop(){
    clear(C_BLACK);drawTaskbar();
    for(int i=0;i<ICON_COUNT;i++){
        fRect(icons[i].x,icons[i].y,36,40,icons[i].color);
        int tw=strlen(icons[i].name)*6;
        dTxt(icons[i].x+(36-tw)/2,icons[i].y+16,icons[i].name,C_WHITE);
    }
    dTxt(10,118,"FN+arrows=move  ENTER=click",C_LGRAY);
    dTxt(10,130,"FN+ESC=back",C_LGRAY);
}

// ============================================================
// DEBUG SCREEN — shows raw keyboard state
// ============================================================
static bool showDebug = true;
static char lastDetectedChar = 0;
static int lastDetectedKey = 0;
static uint32_t lastKeyTime = 0;

static void drawDebug(){
    if(!showDebug) return;
    fRect(0,100,240,35,C_BLACK);
    dRect(0,100,240,35,C_LGRAY);
    char buf[80];
    snprintf(buf,80,"FN:%d SH:%d CT:%d M5:%d", fnHeld, shiftHeld, ctrlHeld, M5Cardputer.Keyboard.isPressed());
    dTxt(4,102,buf,C_WHITE);
    snprintf(buf,80,"char='%c' (0x%02X) key=%d", lastDetectedChar?lastDetectedChar:'-', (uint8_t)lastDetectedChar, lastDetectedKey);
    dTxt(4,112,buf,C_WHITE);
    uint32_t ago = millis() - lastKeyTime;
    snprintf(buf,80,"last: %lu ms ago", ago);
    dTxt(4,122,buf,C_YELLOW);
}

// ============================================================
// TERMINAL
// ============================================================
static void termPrint(const char*t){
    if(termLineCount<12){strncpy(termLines[termLineCount],t,79);termLines[termLineCount][79]=0;termLineCount++;}
    else{for(int i=0;i<11;i++)strcpy(termLines[i],termLines[i+1]);strncpy(termLines[11],t,79);termLines[11][79]=0;}
}
static void termExec(const char*cmd){
    char buf[128];snprintf(buf,128,"$ %s",cmd);termPrint(buf);
    if(strcmp(cmd,"help")==0){termPrint("help mem wifi scan");termPrint("connect <ssid> <pass>");termPrint("clear reboot debug about");}
    else if(strcmp(cmd,"mem")==0){snprintf(buf,128,"Free: %.1fKB",ESP.getFreeHeap()/1024.0f);termPrint(buf);}
    else if(strcmp(cmd,"wifi")==0){
        if(wifiConnected){snprintf(buf,128,"SSID: %s",wifiSSID);termPrint(buf);snprintf(buf,128,"IP: %s",WiFi.localIP().toString().c_str());termPrint(buf);}
        else termPrint("Not connected");
    }
    else if(strcmp(cmd,"scan")==0){
        termPrint("Scanning...");wifiScanCount=WiFi.scanNetworks();
        for(int i=0;i<wifiScanCount&&i<15;i++){snprintf(buf,128," %d:%s %ddBm",i+1,WiFi.SSID(i).c_str(),WiFi.RSSI(i));termPrint(buf);}
    }
    else if(strncmp(cmd,"connect ",8)==0){
        char ssid[33]="",pass[65]="";sscanf(cmd+8,"%32s %64s",ssid,pass);
        termPrint("Connecting...");WiFi.disconnect();WiFi.begin(ssid,pass);
        uint32_t t=millis();while(WiFi.status()!=WL_CONNECTED&&millis()-t<10000)delay(200);
        if(WiFi.status()==WL_CONNECTED){strcpy(wifiSSID,ssid);strcpy(wifiPass,pass);
            prefs.begin("os",false);prefs.putString("ssid",ssid);prefs.putString("pass",pass);prefs.end();
            snprintf(buf,128,"OK! %s",WiFi.localIP().toString().c_str());termPrint(buf);wifiConnected=true;}
        else termPrint("FAILED");
    }
    else if(strcmp(cmd,"clear")==0){termLineCount=0;termInputLen=0;termInput[0]=0;}
    else if(strcmp(cmd,"debug")==0){showDebug=!showDebug;termPrint(showDebug?"Debug ON":"Debug OFF");}
    else if(strcmp(cmd,"about")==0){termPrint("CardputerOS v0.5");termPrint("ESP32-S3FN8");}
    else if(strcmp(cmd,"reboot")==0){ESP.restart();}
    else if(strlen(cmd)>0){snprintf(buf,128,"Unknown: %s",cmd);termPrint(buf);}
}
static void drawTerminal(){
    clear(C_BLACK);fRect(0,0,240,14,C_WINTITLE);dTxt(4,2,"Terminal",C_WHITE);dTxt(228,2,"X",C_WHITE);
    int start=termLineCount>10?termLineCount-10:0;int y=18;
    for(int i=start;i<termLineCount&&y<100;i++){dTxt(2,y,termLines[i],C_LGRAY);y+=9;}
    fRect(0,110,240,17,C_DGRAY);dRect(0,110,240,17,C_LGRAY);
    dTxt(4,111,">",C_GREEN);dTxt(14,111,termInput,C_WHITE);
    if((millis()/500)%2==0){int cx=14+termInputLen*6;fRect(cx,111,7,10,C_WHITE);}
}
static void termHandleKey(OsKey k,char ch){
    if(k==K_ENTER){if(termInputLen>0){termExec(termInput);termInputLen=0;termInput[0]=0;}}
    else if(k==K_BSPACE){if(termInputLen>0){termInputLen--;termInput[termInputLen]=0;}}
    else if(ch&&ch>=32&&ch<127&&termInputLen<126){termInput[termInputLen++]=ch;termInput[termInputLen]=0;}
}

// ============================================================
// SETTINGS
// ============================================================
static void drawSettings(){
    clear(C_BLACK);fRect(0,0,240,14,C_WINTITLE);dTxt(4,2,"Settings",C_WHITE);dTxt(228,2,"X",C_WHITE);
    const char*items[]={"WiFi Network","WiFi Password","Brightness","YouTube Proxy","< Back"};
    for(int i=0;i<5;i++){uint16_t bg=(i==settingsRow)?C_BLUE:C_DGRAY;fRect(10,18+i*18,220,17,bg);dTxt(14,19+i*18,items[i],C_WHITE);
        if(i==0)dTxt(100,19+i*18,wifiSSID[0]?wifiSSID:"not set",C_LGRAY);
        if(i==2){char s[8];snprintf(s,8,"%d",brightness);dTxt(200,19+i*18,s,C_LGRAY);}
        if(i==3){char s[40];snprintf(s,36,"%.34s",ytWorkerUrl);dTxt(14,30+i*18,s,C_LGRAY);}}
}
static void settingsHandleKey(OsKey k){
    if(k==K_UP)settingsRow=(settingsRow>0)?settingsRow-1:4;
    else if(k==K_DOWN)settingsRow=(settingsRow<4)?settingsRow+1:0;
    else if(k==K_ENTER){
        if(settingsRow==4){currentApp=APP_DESKTOP;drawDesktop();}
        else if(settingsRow==2){brightness=(brightness>=224)?32:brightness+32;M5Cardputer.Display.setBrightness(brightness);}
        else if(settingsRow==0){currentApp=APP_WIFI;wifiScanning=true;}
        else if(settingsRow==3){
            // Toggle Worker on/off
            if(ytWorkerUrl[0]==0) strcpy(ytWorkerUrl,"https://yt-proxy.mikem1.workers.dev");
            else ytWorkerUrl[0]=0;
            prefs.begin("os",false);prefs.putString("ytProxy",ytWorkerUrl);prefs.end();
        }
    }
    else if(k==K_ESC){currentApp=APP_DESKTOP;drawDesktop();}
}

// ============================================================
// WIFI SCANNER
// ============================================================
static void drawWifiScan(){
    clear(C_BLACK);fRect(0,0,240,14,C_WINTITLE);dTxt(4,2,"WiFi",C_WHITE);dTxt(228,2,"X",C_WHITE);
    if(wifiScanning){dTxt(50,60,"Scanning...",C_CYAN);M5Cardputer.Display.display();
        wifiScanCount=WiFi.scanNetworks();
        for(int i=0;i<wifiScanCount&&i<20;i++){
            wifiScanNames[i]=WiFi.SSID(i);
            wifiScanEncrypted[i]=(WiFi.encryptionType(i)!=WIFI_AUTH_OPEN);
        }
        wifiScanning=false;}
    for(int i=0;i<wifiScanCount&&i<9;i++){uint16_t bg=(i==wifiScanSel)?C_BLUE:C_DGRAY;fRect(5,16+i*12,230,11,bg);
        char s[80];snprintf(s,80,"%s %s %ddBm",wifiScanNames[i].c_str(),wifiScanEncrypted[i]?"[*]":"[open]",WiFi.RSSI(i));dTxt(8,17+i*12,s,C_WHITE);}
}
static void drawWifiInput(){
    clear(C_BLACK);fRect(0,0,240,14,C_WINTITLE);dTxt(4,2,"WiFi Password",C_WHITE);dTxt(228,2,"X",C_WHITE);
    dTxt(10,24,"Network:",C_LGRAY);dTxt(10,36,wifiScanNames[wifiScanSel].c_str(),C_WHITE);
    
    if(wifiStatus==1) {
        // Connecting...
        dTxt(50,55,"Connecting...",C_CYAN);
        dTxt(10,75,wifiSSID,C_WHITE);
        // Animated dots
        int dots=(millis()/400)%4; char dotStr[8]=""; for(int i=0;i<dots;i++) strcat(dotStr,".");
        dTxt(130,55,dotStr,C_CYAN);
        dTxt(30,100,"Please wait...",C_LGRAY);
    } else if(wifiStatus==2) {
        // Success!
        dTxt(30,45,"Connected!",C_GREEN);
        char ipBuf[32]; snprintf(ipBuf,32,"IP: %s",WiFi.localIP().toString().c_str());
        dTxt(30,65,ipBuf,C_WHITE);
        dTxt(30,90,"ENTER=back",C_LGRAY);
    } else if(wifiStatus==3) {
        // Failed
        dTxt(30,45,"FAILED!",C_RED);
        dTxt(30,65,"Wrong password or",C_LGRAY);
        dTxt(30,77,"network unreachable",C_LGRAY);
        dTxt(30,100,"ENTER=retry  ESC=back",C_LGRAY);
    } else {
        // Typing mode
        dTxt(10,54,"Password:",C_LGRAY);
        fRect(10,66,220,16,C_DGRAY);dRect(10,66,220,16,C_LGRAY);
        dTxt(14,68,wifiInputBuf,C_WHITE);
        if((millis()/500)%2==0){int cx=14+wifiInputLen*7;fRect(cx,67,8,14,C_WHITE);}
        fRect(10,90,100,16,C_GREEN);dTxt(14,92,"Connect",C_BLACK);
        fRect(120,90,100,16,C_RED);dTxt(124,92,"Cancel",C_WHITE);
        dTxt(10,115,"Type password, ENTER=connect",C_LGRAY);
    }
}
static void wifiConnectWithPass(){
    strcpy(wifiPass, wifiInputBuf);  // Copy typed password to connection buffer
    wifiStatus=1;drawWifiInput();M5Cardputer.Display.display();
    WiFi.disconnect();WiFi.begin(wifiSSID,wifiPass);
    uint32_t t=millis();
    while(WiFi.status()!=WL_CONNECTED&&millis()-t<10000){
        drawWifiInput();M5Cardputer.Display.display();
        delay(500);
    }
    if(WiFi.status()==WL_CONNECTED){
        wifiConnected=true;
        prefs.begin("os",false);prefs.putString("ssid",wifiSSID);prefs.putString("pass",wifiPass);prefs.end();
        wifiStatus=2;
    } else {
        wifiStatus=3;
    }
    drawWifiInput();
}
static void wifiScanHandleKey(OsKey k, char ch){
    // Password input mode
    if(wifiInputMode){
        if(wifiStatus==2) {
            // Success — ENTER goes back to settings
            if(k==K_ENTER){wifiInputMode=false;wifiStatus=0;currentApp=APP_SETTINGS;drawSettings();}
            return;
        }
        if(wifiStatus==3) {
            // Failed — ENTER retries, ESC goes back
            if(k==K_ENTER){wifiInputMode=false;wifiStatus=0;}
            else if(k==K_ESC){wifiInputMode=false;wifiStatus=0;currentApp=APP_SETTINGS;}
            return;
        }
        if(k==K_ENTER){wifiConnectWithPass();}
        else if(k==K_BSPACE){if(wifiInputLen>0){wifiInputLen--;wifiInputBuf[wifiInputLen]=0;}}
        else if(ch&&ch>=32&&ch<127&&wifiInputLen<63){wifiInputBuf[wifiInputLen++]=ch;wifiInputBuf[wifiInputLen]=0;}
        return;
    }
    // Network list mode
    if(k==K_UP)wifiScanSel=(wifiScanSel>0)?wifiScanSel-1:0;
    else if(k==K_DOWN&&wifiScanCount>0)wifiScanSel=(wifiScanSel<wifiScanCount-1)?wifiScanSel+1:0;
    else if(k==K_ENTER&&wifiScanSel<wifiScanCount){
        strcpy(wifiSSID,wifiScanNames[wifiScanSel].c_str());
        if(wifiScanEncrypted[wifiScanSel]){
            // Encrypted → show password input
            wifiInputBuf[0]=0;wifiInputLen=0;wifiInputMode=true;
        } else {
            // Open → connect directly
            wifiPass[0]=0;
            wifiConnectWithPass();
            currentApp=APP_SETTINGS;
        }
    }
    else if(k==K_ESC){currentApp=APP_SETTINGS;}
}

// ============================================================
// YOUTUBE — Piped API (search + video info + thumbnails)
// ============================================================

// Simple JSON helpers
static int jsonFind(const char* json, const char* key, char* val, int valSize) {
    char pattern[64]; snprintf(pattern,64,"\"%s\":",key);
    const char* p = strstr(json, pattern); if(!p) return 0;
    p += strlen(pattern);
    while(*p==' ') p++;
    if(*p=='"') { p++; int i=0; while(*p&&*p!='"'&&i<valSize-1){val[i++]=*p++;} val[i]=0; return i; }
    int i=0; while(*p&&*p!=','&&*p!='}'&&*p!=']'&&i<valSize-1){
        if(*p==' '||*p=='\n'||*p=='\r'||*p=='\t'){p++;continue;}
        val[i++]=*p++;} val[i]=0; return i;
}
static int jsonFindInt(const char* json, const char* key) { char v[32]; jsonFind(json,key,v,32); return atoi(v); }
static void ytFetchUrl(const char* path, char* buf, int bufSize) {
    // Build URL: use companion server for everything (search + streams)
    char url[300];
    if(ytServerIP[0]) {
        snprintf(url,300,"https://%s%s",ytServerIP,path);
    } else if(ytWorkerUrl[0]) {
        snprintf(url,300,"%s%s",ytWorkerUrl,path);
    } else {
        snprintf(url,300,"https://api.piped.private.coffee%s",path);
    }
    WiFiClientSecure client; client.setInsecure();
    HTTPClient http;
    http.begin(client, url); http.setTimeout(10000);
    http.setUserAgent("CardputerOS/0.5");
    http.addHeader("Accept", "application/json");
    int code = http.GET();
    if(code==200){
        String s = http.getString();
        int len = s.length(); if(len>bufSize-1) len=bufSize-1;
        memcpy(buf, s.c_str(), len); buf[len]=0;
    } else { buf[0]=0; }
    http.end();
}
static void ytFetchBinary(const char* url, uint8_t* buf, int bufSize, int* outSize) {
    WiFiClientSecure client; client.setInsecure();
    HTTPClient http;
    http.begin(client, url); http.setTimeout(10000);
    http.setUserAgent("CardputerOS/0.5");
    int code = http.GET(); *outSize=0;
    if(code==200){
        int len = http.getSize();
        if(len>bufSize) len=bufSize;
        WiFiClient* stream = http.getStreamPtr();
        if(stream) { *outSize = stream->readBytes(buf, len); }
    }
    http.end();
}

// Extract video ID from "/watch?v=XXXXX"
static void ytExtractId(const char* url, char* id, int idSize) {
    const char* p = strstr(url, "v="); if(!p){id[0]=0;return;}
    p+=2; int i=0; while(*p&&*p!='&'&&*p!='"'&&i<idSize-1){id[i++]=*p++;} id[i]=0;
}
// Format seconds to mm:ss
static void ytFmtDuration(int secs, char* buf, int bufSize) {
    snprintf(buf,bufSize,"%d:%02d",secs/60,secs%60);
}

// === YouTube Search ===
static void ytSearch() {
    if(!wifiConnected||!ytQuery[0]) return;
    dTxt(80,65,"Searching...",C_CYAN); M5Cardputer.Display.display();
    
    static char jsonBuf[6000];
    ytResultCount=0; ytResultSel=0;
    
    // Fetch via Worker or direct Piped
    char path[256]; snprintf(path,256,"/search?q=%s&filter=videos",ytQuery);
    jsonBuf[0]=0;
    ytFetchUrl(path, jsonBuf, sizeof(jsonBuf));
    
    if(!jsonBuf[0]) return;
    
    // Parse items array - find each item block
    const char* p = jsonBuf;
    for(int n=0; n<10; n++) {
        const char* itemStart = strstr(p, "\"url\":\"/watch?v=");
        if(!itemStart) break;
        itemStart += 16; // skip past "url":"/watch?v= to video ID
        // Extract video ID
        int i=0; while(*itemStart&&*itemStart!='"'&&i<11){ytResults[n].id[i++]=*itemStart++;} ytResults[n].id[i]=0;
        if(!ytResults[n].id[0]) { p=itemStart; continue; }
        // Find title
        const char* titleP = strstr(itemStart, "\"title\":\"");
        if(titleP) { titleP+=9; i=0; while(*titleP&&*titleP!='"'&&i<63){ytResults[n].title[i++]=*titleP++;} ytResults[n].title[i]=0; }
        else ytResults[n].title[0]=0;
        // Find uploaderName
        const char* chP = strstr(itemStart, "\"uploaderName\":\"");
        if(chP) { chP+=16; i=0; while(*chP&&*chP!='"'&&i<31){ytResults[n].channel[i++]=*chP++;} ytResults[n].channel[i]=0; }
        else ytResults[n].channel[0]=0;
        // Thumbnail (JPEG from proxy with auth)
        const char* thP = strstr(itemStart, "\"thumbnail\":\"");
        if(thP) { thP+=13; int i2=0; while(*thP&&*thP!='"'&&i2<199){ytResults[n].thumb[i2++]=*thP++;} ytResults[n].thumb[i2]=0; }
        else ytResults[n].thumb[0]=0;
        // Duration
        ytResults[n].duration = jsonFindInt(itemStart, "duration");
        // Views
        ytResults[n].views = jsonFindInt(itemStart, "views");
        ytResultCount++;
        p = strstr(itemStart, "\"type\":\"stream\"") ? strstr(itemStart, "\"type\":\"stream\"") + 15 : itemStart + 100;
    }
}

// === YouTube Player — fetch video info + thumbnail ===
static void ytLoadVideo(const char* videoId) {
    if(!wifiConnected||!videoId[0]) return;
    ytPlayerState = YT_LOADING;
    ytFreeThumb();
    drawYouTube(); M5Cardputer.Display.display();
    
    // Fetch stream info via Worker or direct
    char path[256]; snprintf(path,256,"/streams/%s",videoId);
    static char infoBuf[4000];
    ytFetchUrl(path, infoBuf, sizeof(infoBuf));
    if(!infoBuf[0]) { ytPlayerState=YT_IDLE; return; }
    
    // Parse title
    jsonFind(infoBuf, "title", ytPlayTitle, sizeof(ytPlayTitle));
    ytPlayDuration = jsonFindInt(infoBuf, "duration");
    ytPlayViews = jsonFindInt(infoBuf, "views");
    
    // Build JPEG thumbnail URL - use proxy from search results if available
    // Find the thumbnail from the selected search result
    ytPlayThumbUrl[0]=0;
    for(int i=0;i<ytResultCount;i++){
        if(strcmp(ytResults[i].id, videoId)==0 && ytResults[i].thumb[0]){
            strncpy(ytPlayThumbUrl, ytResults[i].thumb, sizeof(ytPlayThumbUrl)-1);
            break;
        }
    }
    if(!ytPlayThumbUrl[0]){
        // Fallback: construct proxy URL
        snprintf(ytPlayThumbUrl, sizeof(ytPlayThumbUrl),
            "https://proxy.piped.private.coffee/vi/%s/hqdefault.jpg?host=i.ytimg.com", videoId);
    }
    
    // Parse storyboard (sprite sheets for "video" preview)
    ytSb={}; ytSbCurFrame=0;
    const char* sb = strstr(infoBuf, "\"storyboards\"");
    if(!sb) sb = strstr(infoBuf, "\"previewFrames\"");
    if(sb) {
        // Find first storyboard URL
        const char* urlP = strstr(sb, "\"urls\"");
        if(urlP) {
            urlP = strstr(urlP, "\"http");
            if(!urlP) urlP = strstr(urlP, "\"https");
            if(urlP) {
                urlP++; // skip opening quote
                int i=0; while(*urlP&&*urlP!='"'&&i<199){ytSb.url[i++]=*urlP++;} ytSb.url[i]=0;
                ytSb.frameW = jsonFindInt(sb, "frameWidth");
                ytSb.frameH = jsonFindInt(sb, "frameHeight");
                ytSb.total = jsonFindInt(sb, "totalCount");
                ytSb.durPerFrame = jsonFindInt(sb, "durationPerFrame");
                ytSb.perRow = jsonFindInt(sb, "framesPerPageX");
                ytSb.perCol = jsonFindInt(sb, "framesPerPageY");
                if(ytSb.frameW==0) ytSb.frameW=80;
                if(ytSb.frameH==0) ytSb.frameH=45;
                if(ytSb.durPerFrame==0) ytSb.durPerFrame=2000;
                if(ytSb.perRow==0) ytSb.perRow=10;
                if(ytSb.perCol==0) ytSb.perCol=10;
            }
        }
    }
    ytPlayVideoUrl[0]=0;
    const char* vs = strstr(infoBuf, "\"videoStreams\"");
    if(vs) {
        // Find "videoOnly":false
        const char* vo = strstr(vs, "\"videoOnly\":false");
        if(vo) {
            // Go back to find the "url":" of this stream
            const char* block = vo - 500; if(block < vs) block = vs;
            const char* urlP = vo;
            while(urlP > block && strncmp(urlP-6, "\"url\":\"", 7)!=0) urlP--;
            if(urlP > block) { urlP++; int i=0; while(*urlP&&*urlP!='"'&&i<sizeof(ytPlayVideoUrl)-1){ytPlayVideoUrl[i++]=*urlP++;} ytPlayVideoUrl[i]=0; }
        }
    }
    
    // Fetch thumbnail
    if(ytPlayThumbUrl[0]) {
        ytThumbBuf = (uint8_t*)malloc(30000);
        if(ytThumbBuf) {
            int sz=0; ytFetchBinary(ytPlayThumbUrl, ytThumbBuf, 30000, &sz);
            ytThumbSize = sz;
            if(ytThumbSize < 100) { free(ytThumbBuf); ytThumbBuf=nullptr; ytThumbSize=0; }
        }
    }
    ytPlayerState = YT_PLAYING;
}

static void ytFreeThumb() {
    if(ytThumbBuf){free(ytThumbBuf); ytThumbBuf=nullptr; ytThumbSize=0;}
}

// === YouTube Draw ===
static enum {YTS_INPUT, YTS_RESULTS, YTS_PLAYER, YTS_STREAMING} ytScreen = YTS_INPUT;

static void ytStopStream() {
    if(ytStreaming){ytStreaming=false;ytHttp.end();ytStreamClient.stop();}
}

// Read HTTP status code AND save Location header
static char ytRedirectURL[256]="";
static int ytReadHTTPStatus() {
    ytRedirectURL[0]=0;
    uint32_t start = millis();
    // Wait for first data — server may need time for yt-dlp extraction
    while(!ytStreamClient.available() && ytStreamClient.connected() && millis()-start < 45000) {
        delay(100);
    }
    // Read status line
    int status = 0;
    char lineBuf[256]=""; int linePos=0;
    bool firstLine = true;
    while(ytStreamClient.connected()) {
        while(!ytStreamClient.available() && millis()-start < 30000) { delay(10); }
        if(!ytStreamClient.available()) break;
        char c = ytStreamClient.read();
        if(c=='\r') continue;
        if(c=='\n') {
            lineBuf[linePos]=0;
            if(firstLine && linePos>10) {
                // "HTTP/1.1 200 OK" or "HTTP/1.1 308 ..."
                char* sp = strchr(lineBuf,' ');
                if(sp) status = atoi(sp+1);
                firstLine = false;
            } else if(strncasecmp(lineBuf,"Location:",9)==0) {
                char* p = lineBuf+9; while(*p==' ')p++;
                strncpy(ytRedirectURL,p,255);
            }
            if(linePos==0) break; // Empty line = end of headers
            linePos = 0;
        } else {
            if(linePos<255) lineBuf[linePos++]=c;
        }
    }
    return status;
}

// Stream MJPEG frames
static int ytFramesDrawn = 0;
static int ytLastStatus = 0;
static void ytUpdateStream() {
    if(!ytStreaming) return;
    if(!ytStreamClient.connected()){ytStopStream();return;}
    size_t avail = ytStreamClient.available();
    if(!avail) {
        // Status every 2s
        static uint32_t lastSt = 0;
        if(millis()-lastSt > 2000) {
            lastSt = millis();
            Serial.printf("[STREAM] No data. connected=%d\n", ytStreamClient.connected());
            fRect(0,120,240,15,C_DGRAY);
            char msg[48]; snprintf(msg,48,"frames:%d bytes:%d", ytFramesDrawn, (int)ytFrameDataPos);
            dTxt(4,122,msg,C_YELLOW);
            M5Cardputer.Display.display();
        }
        return;
    }
    uint8_t buf[1024];
    size_t n = ytStreamClient.read(buf, sizeof(buf));
    Serial.printf("[STREAM] Read %d bytes\n", n);
    for(size_t i=0;i<n;i++){
        uint8_t b=buf[i];
        if(!ytInFrame){
            if(ytFrameDataPos==0&&b==0xFF){ytFrameData[0]=b;ytFrameDataPos=1;}
            else if(ytFrameDataPos==1&&b==0xD8){ytFrameData[1]=b;ytFrameDataPos=2;ytInFrame=true;}
            else ytFrameDataPos=0;
        } else {
            if(ytFrameDataPos<sizeof(ytFrameData)) ytFrameData[ytFrameDataPos++]=b;
            if(ytFrameDataPos>100&&ytFrameData[ytFrameDataPos-2]==0xFF&&ytFrameData[ytFrameDataPos-1]==0xD9){
                bool ok = M5Cardputer.Display.drawJpg(ytFrameData,ytFrameDataPos,0,0,240,135,0,0,1.0f);
                Serial.printf("[STREAM] Frame #%d: %d bytes, drawJpg=%d\n", ytFramesDrawn, ytFrameDataPos, ok);
                fRect(0,120,240,15,C_DGRAY);
                char info[50]; snprintf(info,50,"OK:%d %dKB", ok, (int)(ytFrameDataPos/1024));
                dTxt(4,122,info,ok?C_GREEN:C_RED);
                ytFramesDrawn++;
                M5Cardputer.Display.display();
                ytInFrame=false;ytFrameDataPos=0;
            }
            // Buffer overflow protection
            if(ytFrameDataPos >= sizeof(ytFrameData)) { ytInFrame=false; ytFrameDataPos=0; }
        }
    }
}

static void drawYouTube(){
    if(ytScreen!=YTS_STREAMING) { clear(C_BLACK); }
    fRect(0,0,240,14,C_RED); dTxt(4,2,"YouTube",C_WHITE); dTxt(228,2,"X",C_WHITE);
    
    if(ytScreen==YTS_INPUT) {
        dTxt(4,20,"Search:",C_LGRAY);
        fRect(4,32,232,16,C_DGRAY); dRect(4,32,232,16,C_LGRAY);
        dTxt(8,34,ytQuery,C_WHITE);
        if((millis()/500)%2==0){int cx=8+ytQueryLen*6; fRect(cx,33,6,14,C_WHITE);}
        dTxt(4,56,"ENTER=search",C_LGRAY);
        dTxt(4,68,"FN+ESC=back",C_LGRAY);
        if(!wifiConnected){dTxt(30,90,"Connect WiFi first!",C_RED);}
    }
    else if(ytScreen==YTS_RESULTS) {
        if(ytResultCount==0){dTxt(50,60,"No results",C_LGRAY);}
        // Show max 5 items with scroll
        int scrollStart = 0;
        if(ytResultSel >= 5) scrollStart = ytResultSel - 4;
        for(int i=scrollStart;i<ytResultCount&&i<scrollStart+5;i++){
            int y = 16 + (i - scrollStart) * 20;
            uint16_t bg=(i==ytResultSel)?C_BLUE:C_DGRAY;
            fRect(2,y,236,19,bg);
            char dur[8]; ytFmtDuration(ytResults[i].duration,dur,8);
            // Truncate title to fit
            char line[36]; snprintf(line,36,"%.32s",ytResults[i].title);
            char full[42]; snprintf(full,42,"%s [%s]",line,dur);
            dTxt(4,y+1,full,C_WHITE,1);
            char sub[40]; snprintf(sub,40,"%.20s  %dK views",ytResults[i].channel,ytResults[i].views/1000);
            dTxt(4,y+9,sub,C_LGRAY);
            // Draw selection arrow
            if(i==ytResultSel) dTxt(230,y+1,">",C_WHITE);
        }
        dTxt(4,118,"ENTER=play",C_CYAN);
        dTxt(100,118,"FN+Up/Dn=nav",C_LGRAY);
        dTxt(4,128,"ESC=back",C_LGRAY);
    }
    else if(ytScreen==YTS_PLAYER) {
        if(ytPlayerState==YT_LOADING) {
            dTxt(70,60,"Loading...",C_CYAN);
        } else if(ytPlayerState==YT_PLAYING) {
            // Show thumbnail or storyboard frame
            if(ytThumbBuf&&ytThumbSize>100) {
                M5Cardputer.Display.drawJpg(ytThumbBuf,ytThumbSize,0,16,240,100,0,0,1.0f);
            } else {
                fRect(0,16,240,100,C_DGRAY);
                dTxt(50,60,"No thumbnail",C_LGRAY);
            }
            // Info bar
            fRect(0,116,240,19,C_DGRAY);
            char info[40]; snprintf(info,40,"%.35s",ytPlayTitle);
            dTxt(4,118,info,C_WHITE);
            char sub[60]; char dur[8]; ytFmtDuration(ytPlayDuration,dur,8);
            snprintf(sub,60,"%s %s %dK views",ytPlayChannel,dur,ytPlayViews/1000);
            dTxt(4,128,sub,C_LGRAY);
            // Show storyboard indicator
            if(ytSb.url[0]) dTxt(200,118,"SB",C_CYAN);
            dTxt(4,118,"ENTER=play on server",C_CYAN);
        }
    }
    else if(ytScreen==YTS_STREAMING) {
        // MJPEG frames are drawn by ytUpdateStream() directly
        // Just show minimal overlay
        fRect(0,0,240,10,C_RED); dTxt(4,1,"LIVE",C_WHITE);
    }
}

// === YouTube Key Handler ===
static void ytHandleKey(OsKey k, char ch) {
    if(ytScreen==YTS_INPUT) {
        if(k==K_ENTER && ytQueryLen>0 && wifiConnected) {
            ytSearch();
            ytScreen=YTS_RESULTS;
            drawYouTube();
        }
        else if(k==K_BSPACE && ytQueryLen>0) { ytQueryLen--; ytQuery[ytQueryLen]=0; }
        else if(ch&&ch>=32&&ch<127&&ytQueryLen<126) { ytQuery[ytQueryLen++]=ch; ytQuery[ytQueryLen]=0; }
        else if(k==K_ESC) { currentApp=APP_DESKTOP; drawDesktop(); }
    }
    else if(ytScreen==YTS_RESULTS) {
        if(k==K_UP) ytResultSel=(ytResultSel>0)?ytResultSel-1:0;
        else if(k==K_DOWN&&ytResultCount>0) ytResultSel=(ytResultSel<ytResultCount-1)?ytResultSel+1:0;
        else if(k==K_ENTER&&ytResultSel<ytResultCount) {
            ytScreen=YTS_PLAYER;
            drawYouTube(); M5Cardputer.Display.display();
            ytLoadVideo(ytResults[ytResultSel].id);
            drawYouTube();
        }
        else if(k==K_ESC) { ytScreen=YTS_INPUT; drawYouTube(); }
    }
    else if(ytScreen==YTS_PLAYER) {
        if(k==K_ESC) { ytStopStream(); ytFreeThumb(); ytScreen=YTS_RESULTS; drawYouTube(); }
        else if(k==K_ENTER && !ytStreaming && ytResults[ytResultSel].id[0]) {
            ytScreen=YTS_STREAMING;
            // Step 1: Wake up server with simple HTTP request
            bool awake = false;
            for(int attempt=0; attempt<10 && !awake; attempt++) {
                clear(C_BLACK);
                dTxt(30,20,"YouTube Stream",C_RED);
                dTxt(30,45,"Waking server...",C_CYAN);
                char msg[40]; snprintf(msg,40,"Attempt %d/10",attempt+1);
                dTxt(30,60,msg,C_LGRAY);
                M5Cardputer.Display.display();
                // Simple GET to /api/scan to wake Render
                WiFiClientSecure probe; probe.setInsecure();
                HTTPClient http;
                String wakeUrl = String("https://") + ytServerIP + "/api/scan";
                http.begin(probe, wakeUrl);
                http.setTimeout(30000);
                int code = http.GET();
                http.end();
                probe.stop();
                if(code == 200) { awake = true; }
                else {
                    fRect(30,75,200,20,C_BLACK);
                    char err[30]; snprintf(err,30,"Status: %d, retrying...",code);
                    dTxt(30,75,err,C_YELLOW);
                    M5Cardputer.Display.display();
                    delay(5000);
                }
            }
            if(!awake) {
                clear(C_BLACK);
                dTxt(30,50,"Server not reachable",C_RED);
                dTxt(30,70,"Check your internet",C_LGRAY);
                M5Cardputer.Display.display();
                delay(3000);
                ytScreen=YTS_PLAYER; drawYouTube();
                return;
            }
            // Step 2: Server is awake — start MJPEG stream directly
            clear(C_BLACK);
            dTxt(30,50,"Server awake!",C_GREEN);
            dTxt(30,70,"Connecting...",C_CYAN);
            M5Cardputer.Display.display();
            Serial.println("[STREAM] Connecting to server...");
            ytStreamClient.stop();
            ytStreamClient.setInsecure();
            ytStreamClient.setTimeout(30000);
            if(ytStreamClient.connect(ytServerIP, 443)) {
                char req[256]; snprintf(req,256,"GET /api/stream/%s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n",ytResults[ytResultSel].id,ytServerIP);
                Serial.printf("[STREAM] Sending: %s", req);
                ytStreamClient.print(req);
                ytLastStatus = ytReadHTTPStatus();
                Serial.printf("[STREAM] HTTP status: %d\n", ytLastStatus);
                if(ytLastStatus == 200) {
                    ytStreaming=true; ytInFrame=false; ytFrameDataPos=0; ytFramesDrawn=0;
                } else if(ytLastStatus == 308 && ytRedirectURL[0]) {
                    // Follow redirect — strip trailing slash to avoid 404
                    ytStreamClient.stop();
                    String locStr = String(ytRedirectURL);
                    while(locStr.endsWith("/")) locStr.remove(locStr.length()-1);
                    int protoEnd = locStr.indexOf("://");
                    int hostStart = (protoEnd>=0) ? protoEnd+3 : 0;
                    int hostEnd = locStr.indexOf("/", hostStart);
                    String host = locStr.substring(hostStart, hostEnd);
                    String path = locStr.substring(hostEnd);
                    if(ytStreamClient.connect(host.c_str(), 443)) {
                        snprintf(req,256,"GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n",path.c_str(),host.c_str());
                        ytStreamClient.print(req);
                        ytLastStatus = ytReadHTTPStatus();
                        if(ytLastStatus == 200) {
                            ytStreaming=true; ytInFrame=false; ytFrameDataPos=0; ytFramesDrawn=0;
                        }
                    }
                }
            }
            if(!ytStreaming) {
                clear(C_BLACK);
                dTxt(30,50,"Stream failed",C_RED);
                M5Cardputer.Display.display();
                delay(2000);
                ytScreen=YTS_PLAYER; drawYouTube();
            }
        }
    }
    else if(ytScreen==YTS_STREAMING) {
        if(k==K_ESC || k==K_SPACE) { ytStopStream(); ytScreen=YTS_PLAYER; drawYouTube(); }
    }
}

// ============================================================
// KEY MAP
// ============================================================
static OsKey mapKey(char c){
    // Use direct mapping (enum values are NOT alphabetical due to SHIFT/FN/CTRL in between)
    switch(c){
        case ' ':return K_SPACE; case '\n':return K_ENTER; case '\b':return K_BSPACE;
        case '\t':return K_TAB; case '-':return K_MINUS; case '=':return K_EQUAL;
        case '[':return K_LBR; case ']':return K_RBR; case '\\':return K_BSLASH;
        case ';':return K_SCOL; case '\'':return K_QUOTE; case ',':return K_COMMA;
        case '.':return K_DOT; case '/':return K_SLASH;
        case '`':case '~':return K_NONE;
        case '0':return K_0; case '1':return K_1; case '2':return K_2;
        case '3':return K_3; case '4':return K_4; case '5':return K_5;
        case '6':return K_6; case '7':return K_7; case '8':return K_8;
        case '9':return K_9;
        case 'a':case 'A':return K_A; case 'b':case 'B':return K_B;
        case 'c':case 'C':return K_C; case 'd':case 'D':return K_D;
        case 'e':case 'E':return K_E; case 'f':case 'F':return K_F;
        case 'g':case 'G':return K_G; case 'h':case 'H':return K_H;
        case 'i':case 'I':return K_I; case 'j':case 'J':return K_J;
        case 'k':case 'K':return K_K; case 'l':case 'L':return K_L;
        case 'm':case 'M':return K_M; case 'n':case 'N':return K_N;
        case 'o':case 'O':return K_O; case 'p':case 'P':return K_P;
        case 'q':case 'Q':return K_Q; case 'r':case 'R':return K_R;
        case 's':case 'S':return K_S; case 't':case 'T':return K_T;
        case 'u':case 'U':return K_U; case 'v':case 'V':return K_V;
        case 'w':case 'W':return K_W; case 'x':case 'X':return K_X;
        case 'y':case 'Y':return K_Y; case 'z':case 'Z':return K_Z;
        default:return K_NONE;
    }
}

static OsKey scanKeyboard(char* ch){
    *ch = 0;
    M5Cardputer.update();
    if(!M5Cardputer.Keyboard.isPressed()) {
        fnHeld = false; shiftHeld = false; ctrlHeld = false;
        return K_NONE;
    }

    Keyboard_Class::KeysState ks = M5Cardputer.Keyboard.keysState();
    fnHeld = ks.fn; shiftHeld = ks.shift; ctrlHeld = ks.ctrl;

    // FN layer: arrow keys
    if(ks.fn) {
        if(ks.up) return K_UP;
        if(ks.down) return K_DOWN;
        if(ks.left) return K_LEFT;
        if(ks.right) return K_RIGHT;
        if(ks.esc) return K_ESC;
        return K_NONE;  // FN + other = ignore
    }

    // Special keys (non-FN layer)
    if(ks.enter) return K_ENTER;
    if(ks.backspace) return K_BSPACE;
    if(ks.tab) return K_TAB;
    if(ks.esc) return K_ESC;
    if(ks.del) return K_BSPACE;

    // SPACE
    if(ks.space){*ch = ' '; return K_SPACE;}

    // Brute-force scan all printable characters using isKeyPressed()
    // This bypasses the broken ks.word vector
    static const char allKeys[] = "qwertyuiopasdfghjklzxcvbnm1234567890-=[]\\;',./`~!@#$%^&*()_+{}|:\"<>?";
    bool shiftActive = ks.shift || ctrlHeld;
    for(int i = 0; i < (int)sizeof(allKeys)-1; i++) {
        if(M5Cardputer.Keyboard.isKeyPressed(allKeys[i])) {
            char c = allKeys[i];
            // If shift is active, uppercase letters
            if(shiftActive && c >= 'a' && c <= 'z') c = c - 32;
            *ch = c;
            return mapKey(c);
        }
    }

    return K_NONE;
}

// ============================================================
// BOOT
// ============================================================
static void bootScreen(){
    clear(C_BLACK);    dTxt(30,15,"CardputerOS",C_CYAN,2);dTxt(60,45,"v0.6.0",C_WHITE);
    dTxt(10,65,"ESP32-S3 240MHz",C_LGRAY);
    char s[64];snprintf(s,64,"Flash:%dMB Free:%.0fKB",ESP.getFlashChipSize()/(1024*1024),ESP.getFreeHeap()/1024.0f);
    dTxt(10,77,s,C_LGRAY);
    dTxt(10,95,"Keyboard GPIO Test:",C_CYAN);
    dTxt(10,107,"Press any key on keyboard...",C_WHITE);
    fRect(19,120,202,6,C_DGRAY);
    for(int i=0;i<=200;i+=3){fRect(20,121,i,4,C_CYAN);delay(5);}
}

// ============================================================
// SETUP
// ============================================================
void setup(){
    Serial.begin(115200);
    Serial.println("\n=== CardputerOS v0.3 ===");

    evtInit();
    auto cfg=M5.config();
    M5Cardputer.begin(cfg,true);
    M5Cardputer.Display.setRotation(1);
    M5Cardputer.Display.setBrightness(255);

    prefs.begin("os",false);
    strcpy(wifiSSID,prefs.getString("ssid","").c_str());
    strcpy(wifiPass,prefs.getString("pass","").c_str());
    brightness=prefs.getInt("brightness",255);
    strcpy(ytWorkerUrl,prefs.getString("ytProxy","").c_str());
    prefs.end();

    bootScreen();
    delay(500);

    // Auto WiFi
    if(wifiSSID[0]){
        WiFi.disconnect();WiFi.begin(wifiSSID,wifiPass);
        uint32_t t=millis();while(WiFi.status()!=WL_CONNECTED&&millis()-t<8000)delay(100);
        wifiConnected=(WiFi.status()==WL_CONNECTED);
    }

    currentApp=APP_DESKTOP;drawDesktop();
    mouseSetPos(120,67);mouseSetVis(true);
    Serial.println("Ready!");
}

// ============================================================
// LOOP
// ============================================================
static uint32_t lastDraw=0;
void loop(){
    // Reset mouse direction every frame — only set when key IS pressed
    mouseResetDir();

    char ch=0;
    OsKey k=scanKeyboard(&ch);
    uint32_t now = millis();

    // Debounce: only trigger on transition (prevFrame different from current)
    // AND suppress same key within 80ms of last trigger (bounce protection)
    static const uint32_t DEBOUNCE_MS = 80;
    bool keyJustPressed = false;
    if(k != K_NONE) {
        if(k != prevFrameKey) {
            // Edge: key just appeared (was different in previous frame)
            // Extra debounce: was this SAME key triggered very recently?
            if(k == lastKey && (now - keyRepeatStart < DEBOUNCE_MS)) {
                // Bounce — same key reappeared within 80ms of last trigger
            } else {
                // Real new press
                lastKey = k;
                lastChar = ch;
                keyRepeatStart = now;
                keyRepeatLast = now;
                keyJustPressed = true;
            }
        } else {
            // Same key as previous frame — held, repeat for nav/backspace only
            uint32_t heldTime = now - keyRepeatStart;
            uint32_t sinceLastRepeat = now - keyRepeatLast;
            if(heldTime > 400 && sinceLastRepeat > 80) {
                keyRepeatLast = now;
                if(k == K_UP || k == K_DOWN || k == K_LEFT || k == K_RIGHT ||
                   k == K_BSPACE) {
                    keyJustPressed = true;
                }
            }
        }
    }
    prevFrameKey = k;

    // FN+Arrow = mouse movement — must run EVERY frame while held, not on keyJustPressed
    // FN+ESC = back to desktop — same
    if(fnHeld && k!=K_NONE) {
        if(k==K_UP||k==K_DOWN||k==K_LEFT||k==K_RIGHT){
            mouseInput(k, true);
            goto skipKey;
        }
        if(k==K_ESC){
            if(currentApp!=APP_DESKTOP){currentApp=APP_DESKTOP;drawDesktop();}
            goto skipKey;
        }
    }

    if(keyJustPressed && k!=K_NONE){
        lastDetectedChar = ch;
        lastDetectedKey = (int)k;
        lastKeyTime = now;

        // Enter = left click only on Desktop; in apps goes to app handler
        if(k==K_ENTER && currentApp==APP_DESKTOP){
            mouseClickL(true);
            goto skipKey;
        }

        // Backspace in desktop = right click
        if(k==K_BSPACE && currentApp==APP_DESKTOP){
            mouseClickR(true);
            goto skipKey;
        }

        // Everything else goes to current app (including ENTER in apps)
        switch(currentApp){
            case APP_TERMINAL:termHandleKey(k,ch);break;
            case APP_SETTINGS:settingsHandleKey(k);break;
            case APP_WIFI:wifiScanHandleKey(k,ch);break;
            case APP_YOUTUBE:ytHandleKey(k,ch);break;
            default:break;
        }
    }
    skipKey:

    mouseUpdate();
    OsEvent evt;
    while(evtPop(&evt)){
        if(evt.type==3){  // Left click
            int cx = mouseX();
            int cy = mouseY();

            if(currentApp==APP_DESKTOP){
                for(int i=0;i<ICON_COUNT;i++){
                    if(mouseInRect(icons[i].x,icons[i].y,36,40)){
                        currentApp=icons[i].app;
                        if(currentApp==APP_YOUTUBE)drawYouTube();
                        else if(currentApp==APP_TERMINAL){drawTerminal();termInputLen=0;termInput[0]=0;}
                        else if(currentApp==APP_SETTINGS){settingsRow=0;drawSettings();}
                        else if(currentApp==APP_WIFI){wifiScanning=true;drawWifiScan();}
                        break;
                    }
                }
            }
            else if(currentApp==APP_TERMINAL){
                if(mouseInRect(226,0,14,14)){currentApp=APP_DESKTOP;drawDesktop();}
            }
            else if(currentApp==APP_SETTINGS){
                if(mouseInRect(226,0,14,14)){currentApp=APP_DESKTOP;drawDesktop();}
                else {
                    // Click on settings rows
                    for(int i=0;i<5;i++){
                        if(mouseInRect(10,18+i*20,220,18)){
                            settingsRow=i;
                            settingsHandleKey(K_ENTER);
                            break;
                        }
                    }
                }
            }
            else if(currentApp==APP_WIFI){
                if(wifiInputMode){
                    if(mouseInRect(226,0,14,14)){wifiInputMode=false;currentApp=APP_SETTINGS;}
                    else if(mouseInRect(10,88,100,20)){wifiInputMode=false;wifiConnectWithPass();currentApp=APP_SETTINGS;}
                    else if(mouseInRect(120,88,100,20)){wifiInputMode=false;}
                } else {
                    if(mouseInRect(226,0,14,14)){currentApp=APP_SETTINGS;}
                    else {
                        for(int i=0;i<wifiScanCount&&i<9;i++){
                            if(mouseInRect(5,16+i*12,230,11)){
                                wifiScanSel=i;
                                wifiScanHandleKey(K_ENTER,0);
                                break;
                            }
                        }
                    }
                }
            }
            else if(currentApp==APP_YOUTUBE){
                if(mouseInRect(226,0,14,14)){currentApp=APP_DESKTOP;drawDesktop();}
            }
        }
    }

    
    if(now-lastDraw>200){
        lastDraw=now;
        if(!(currentApp==APP_YOUTUBE && ytScreen==YTS_STREAMING)){
            drawTaskbar();
            switch(currentApp){
                case APP_TERMINAL:drawTerminal();break;
                case APP_SETTINGS:drawSettings();break;
                case APP_WIFI:if(wifiInputMode)drawWifiInput();else drawWifiScan();break;
                case APP_YOUTUBE:drawYouTube();break;
                default:break;
            }
            if(showDebug && !(currentApp==APP_YOUTUBE)) drawDebug();
        }
    }

    // MJPEG MUST be last — nothing should draw over it
    ytUpdateStream();
    
    mouseDraw(&M5Cardputer.Display);
    delay(5);
}
