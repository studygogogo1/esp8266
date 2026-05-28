#ifndef SENSOR_READER_H
#define SENSOR_READER_H

#include <DHT.h>
#include "config.h"

// ==================== 全局 DHT 对象声明 ====================
extern DHT dht;

// ==================== 传感器数据结构 ====================
struct SensorData {
    float temperature;     // 温度 (C)
    float humidity;        // 空气湿度 (%)
    float soilMoisture;     // 土壤湿度 (%) 0=最干, 100=最湿
    bool  valid;           // 数据是否有效
};

// ==================== 初始化传感器 ====================
inline void sensorBegin() {
    pinMode(SOIL_PIN, INPUT);
    dht.begin();
    Serial.println("[Sensor] DHT11 初始化完成");
    Serial.println("[Sensor] 土壤湿度传感器初始化完成 (A0)");
}

// ==================== 读取土壤湿度 ====================
// 土壤湿度传感器: 空气中输出最大(~1023), 水中输出最小(~300)
// 需要反向映射: raw 越大 = 越干
inline float readSoilMoisture() {
    int raw = analogRead(SOIL_PIN);

    // 多次采样取平均，减少噪声
    int sum = raw;
    for (int i = 0; i < 4; i++) {
        sum += analogRead(SOIL_PIN);
        delay(10);
    }
    raw = sum / 5;

    // 反向映射: 1023(最干)→0%, 300(最湿)→100%
    float moisture = map(raw, 1023, 300, 0, 100);
    moisture = constrain(moisture, 0, 100);

    Serial.print("[Sensor] 土壤湿度 raw=");
    Serial.print(raw);
    Serial.print(" -> ");
    Serial.print(moisture, 1);
    Serial.println("%");

    return moisture;
}

// ==================== 读取所有传感器数据 ====================
inline SensorData readSensors() {
    SensorData data;
    data.valid = false;

    // 读取 DHT11
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    // 检查 DHT11 是否读取成功
    if (isnan(h) || isnan(t)) {
        Serial.println("[Sensor] DHT11 读取失败! 请检查接线");
        data.temperature = 0;
        data.humidity = 0;
    } else {
        data.temperature = t;
        data.humidity = h;
        data.valid = true;

        Serial.print("[Sensor] 温度: ");
        Serial.print(t, 1);
        Serial.print("C, 湿度: ");
        Serial.print(h, 1);
        Serial.println("%");
    }

    // 读取土壤湿度
    data.soilMoisture = readSoilMoisture();

    return data;
}

#endif // SENSOR_READER_H
