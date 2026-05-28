#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <ESP8266WiFi.h>
#include "config.h"
#include "oled_display.h"

// ==================== WiFi 连接管理 ====================

inline bool wifiConnect() {
    Serial.println("[WiFi] 正在连接...");
    Serial.print("[WiFi] SSID: ");
    Serial.println(WIFI_SSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        oledShowWiFiConnecting(attempts);
        delay(500);
        Serial.print(".");
        attempts++;
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("[WiFi] 连接成功! IP: ");
        Serial.println(WiFi.localIP());
        Serial.print("[WiFi] RSSI: ");
        Serial.println(WiFi.RSSI());
        return true;
    }

    Serial.println("[WiFi] 连接失败!");
    oledShowError("WiFi Failed!");
    return false;
}

inline bool wifiIsConnected() {
    return WiFi.status() == WL_CONNECTED;
}

// 断开重连（在 loop 中调用）
inline void wifiCheckReconnect(unsigned long now) {
    static unsigned long lastCheck = 0;
    if (now - lastCheck < WIFI_RECONNECT_MS) return;
    lastCheck = now;

    if (!wifiIsConnected()) {
        Serial.println("[WiFi] 断开，尝试重连...");
        wifiConnect();
    }
}

#endif // WIFI_MANAGER_H
