#ifndef OLED_DISPLAY_H
#define OLED_DISPLAY_H

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"

// ==================== 全局 OLED 对象声明 ====================
extern Adafruit_SSD1306 display;

// ==================== 初始化函数 ====================
inline void oledBegin() {
    Wire.begin(OLED_SDA, OLED_SCL);
    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
        Serial.println("[OLED] SSD1306 初始化失败!");
        return;
    }
    display.clearDisplay();
    display.display();
    Serial.println("[OLED] SSD1306 初始化成功");
}

// ==================== 显示一行文字 ====================
inline void oledShowLine(int line, const char* text) {
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, line * 16);
    display.println(text);
    display.display();
}

// ==================== 显示启动画面 ====================
inline void oledShowSplash(const char* line1, const char* line2) {
    display.clearDisplay();
    oledShowLine(2, line1);
    oledShowLine(3, line2);
}

// ==================== 显示完整仪表盘 ====================
// 布局:
//   第1行: 温度 + 空气湿度
//   第2行: 土壤湿度
//   第3行: 水泵状态
//   第4行: WiFi信号 + MQTT状态
inline void oledShowDashboard(float temp, float humi, float soil,
                               bool pumpOn, int rssi, bool mqttOk) {
    display.clearDisplay();

    char buf[22];

    // 第1行: T:28.5C H:65%
    snprintf(buf, sizeof(buf), "T:%.1fC H:%.0f%%", temp, humi);
    oledShowLine(0, buf);

    // 第2行: Soil: 25%
    snprintf(buf, sizeof(buf), "Soil: %.0f%%", soil);
    oledShowLine(1, buf);

    // 第3行: Pump: ON / OFF
    snprintf(buf, sizeof(buf), "Pump: %s", pumpOn ? "ON " : "OFF");
    oledShowLine(2, buf);

    // 第4行: WiFi信号 + MQTT状态
    snprintf(buf, sizeof(buf), "%ddBm %s", rssi, mqttOk ? "MQTT:OK" : "MQTT:..");
    oledShowLine(3, buf);
}

// ==================== 显示 WiFi 连接进度 ====================
inline void oledShowWiFiConnecting(int dots) {
    display.clearDisplay();
    char buf[22];
    int dotCount = dots % 16;
    memset(buf, '.', dotCount);
    buf[dotCount] = '\0';
    oledShowLine(0, "Connecting WiFi");
    oledShowLine(1, buf);
}

// ==================== 显示错误信息 ====================
inline void oledShowError(const char* msg) {
    display.clearDisplay();
    oledShowLine(0, "** ERROR **");
    oledShowLine(1, msg);
}

#endif // OLED_DISPLAY_H
