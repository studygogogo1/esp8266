#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WiFiUdp.h>
#include <bearssl/bearssl_hash.h>
#include <bearssl/bearssl_hmac.h>
#include "config.h"
#include "oled_display.h"
#include "pump_controller.h"

// ==================== 全局 MQTT 对象声明 ====================
extern WiFiClient espClient;
extern PubSubClient mqttClient;

// ==================== NTP 时间同步 ====================
// 获取 UTC 时间戳字符串，格式: 20260528T203000Z
inline String ntpGetTimestamp() {
    WiFiUDP ntpUDP;
    const char* ntpServer = "ntp.aliyun.com";
    const int ntpPort = 123;

    ntpUDP.begin(ntpPort);

    // 发送 NTP 请求
    byte packet[48];
    memset(packet, 0, 48);
    packet[0] = 0b11100011; // LI, Version, Mode
    packet[1] = 0;          // Stratum
    packet[2] = 6;          // Polling Interval
    packet[3] = 0xEC;       // Peer Clock Precision

    if (ntpUDP.beginPacket(ntpServer, ntpPort) != 1) {
        ntpUDP.end();
        return "";
    }
    ntpUDP.write(packet, 48);
    ntpUDP.endPacket();

    // 等待响应
    int timeout = 0;
    while (ntpUDP.parsePacket() == 0 && timeout < 10) {
        delay(100);
        timeout++;
    }

    if (ntpUDP.parsePacket() == 0) {
        ntpUDP.end();
        Serial.println("[NTP] 时间同步失败");
        return "";
    }

    ntpUDP.read(packet, 48);
    ntpUDP.end();

    // NTP 时间从 1900年1月1日开始，转换为 Unix 时间戳（1970年起）
    unsigned long highWord = word(packet[40], packet[41]);
    unsigned long lowWord  = word(packet[42], packet[43]);
    unsigned long secsSince1900 = highWord << 16 | lowWord;
    unsigned long unixTime = secsSince1900 - 2208988800UL + NTP_OFFSET;

    // 格式化为 20260528T203000Z
    struct tm* tm_info = gmtime((time_t*)&unixTime);
    char ts[17];
    snprintf(ts, sizeof(ts), "%04d%02d%02dT%02d%02d%02dZ",
             tm_info->tm_year + 1900,
             tm_info->tm_mon + 1,
             tm_info->tm_mday,
             tm_info->tm_hour,
             tm_info->tm_min,
             tm_info->tm_sec);

    Serial.print("[NTP] 时间戳: ");
    Serial.println(ts);
    return String(ts);
}

// ==================== Hex 编码 ====================
inline String hexEncode(const uint8_t* data, size_t len) {
    String result;
    result.reserve(len * 2);
    const char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        result += hex[data[i] >> 4];
        result += hex[data[i] & 0x0F];
    }
    return result;
}

// ==================== 生成 MQTT 密码 ====================
// 华为云 IoTDA: Password = Hex(HMAC-SHA256(key=时间戳, data=设备密钥))
inline String generateMqttPassword(const String& timestamp) {
    br_hmac_key_context kc;
    br_hmac_key_init(&kc, &br_sha256_vtable,
                     timestamp.c_str(), timestamp.length());

    br_hmac_context ctx;
    br_hmac_init(&ctx, &kc, 0);
    br_hmac_update(&ctx, DEVICE_SECRET, strlen(DEVICE_SECRET));

    uint8_t hash[32];
    br_hmac_out(&ctx, hash);

    return hexEncode(hash, 32);
}

// ==================== MQTT 连接 ====================
inline bool mqttConnect() {
    // 获取时间戳
    String timestamp = ntpGetTimestamp();
    if (timestamp.length() == 0) {
        Serial.println("[MQTT] NTP 时间获取失败，无法连接");
        return false;
    }

    // 组装 Client ID: {deviceId}_0_0_{timestamp}
    String clientId = String(DEVICE_ID) + "_0_0_" + timestamp;
    String username = PRODUCT_ID;
    String password = generateMqttPassword(timestamp);

    Serial.println("[MQTT] 正在连接华为云 IoTDA...");
    Serial.print("[MQTT] Client ID: ");
    Serial.println(clientId);
    Serial.print("[MQTT] Username: ");
    Serial.println(username);
    Serial.print("[MQTT] Password (前16字符): ");
    Serial.println(password.substring(0, 16));

    // 设置 TLS（跳过证书验证，测试阶段用）
    espClient.setInsecure();
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setBufferSize(MQTT_BUFFER_SIZE);

    // 连接（PubSubClient 标准 API：connect(clientId, username, password)）
    bool connected = mqttClient.connect(
        clientId.c_str(),
        username.c_str(),
        password.c_str()
    );

    if (connected) {
        Serial.println("[MQTT] 连接成功!");

        // 订阅命令 Topic
        if (mqttClient.subscribe(TOPIC_CMD_SUB)) {
            Serial.print("[MQTT] 已订阅: ");
            Serial.println(TOPIC_CMD_SUB);
        } else {
            Serial.println("[MQTT] 订阅失败!");
        }
        return true;
    }

    Serial.print("[MQTT] 连接失败, 状态码: ");
    Serial.println(mqttClient.state());
    return false;
}

// ==================== MQTT 消息回调 ====================
// 处理华为云下发的命令（水泵控制）
inline void mqttCallback(char* topic, byte* payload, unsigned int length) {
    // 转为字符串
    char msg[128];
    if (length >= sizeof(msg)) length = sizeof(msg) - 1;
    memcpy(msg, payload, length);
    msg[length] = '\0';

    Serial.print("[MQTT] 收到命令 [");
    Serial.print(topic);
    Serial.print("]: ");
    Serial.println(msg);

    // 解析 JSON 命令
    StaticJsonDocument<128> doc;
    DeserializationError err = deserializeJson(doc, msg);

    if (err) {
        Serial.print("[MQTT] JSON 解析失败: ");
        Serial.println(err.c_str());
        return;
    }

    // 检查 pump 命令
    if (doc.containsKey("pump") || doc.containsKey("service_id")) {
        const char* cmd = doc["pump"];
        String result = "success";

        if (cmd && strcmp(cmd, "on") == 0) {
            int duration = doc["duration"] | 30;
            pumpOn(duration);
        } else if (cmd && strcmp(cmd, "off") == 0) {
            pumpOff();
        }

        // 回复命令响应到 commands/response（华为云要求）
        // 从 Topic 中提取 request_id
        String requestId = "";
        const char* reqPos = strstr(topic, "request_id=");
        if (reqPos) {
            requestId = String(reqPos + strlen("request_id="));
        }

        String respTopic = String(TOPIC_CMD_RESP) + requestId;
        StaticJsonDocument<128> reply;
        reply["result_code"] = 0;
        reply["response_name"] = "COMMAND_RESPONSE";
        JsonObject paras = reply.createNestedObject("paras");
        paras["result"] = result;

        char replyBuf[128];
        serializeJson(reply, replyBuf);
        mqttClient.publish(respTopic.c_str(), replyBuf);

        Serial.print("[MQTT] 已回复命令响应 ");
        Serial.print(respTopic);
        Serial.print(": ");
        Serial.println(replyBuf);
    }
}

// ==================== 上报传感器数据到华为云 ====================
inline void mqttReportData(float temp, float humi, float soil,
                            bool pumpOn, int rssi) {
    StaticJsonDocument<512> doc;

    // 华为云 IoTDA 标准格式（必须与 Python 版一致！）
    JsonArray servicesArr = doc.createNestedArray("services");
    JsonObject svc = servicesArr.createNestedObject();
    svc["service_id"] = "sensor_data";
    JsonObject props = svc.createNestedObject("properties");
    props["temperature"]   = temp;
    props["humidity"]      = humi;
    props["soil_moisture"] = soil;
    props["pump_status"]   = pumpOn;
    props["wifi_signal"]   = rssi;
    props["firmware_version"] = FIRMWARE_VERSION;

    char buf[512];
    serializeJson(doc, buf);

    if (mqttClient.publish(TOPIC_MSG_UP, buf)) {
        Serial.print("[MQTT] 数据上报成功: ");
        Serial.println(buf);
    } else {
        Serial.println("[MQTT] 数据上报失败!");
    }
}

// ==================== MQTT 心跳检查与重连 ====================
inline void mqttCheckConnection(unsigned long now) {
    static unsigned long lastCheck = 0;
    if (now - lastCheck < MQTT_RECONNECT_MS) return;
    lastCheck = now;

    if (!mqttClient.connected()) {
        Serial.println("[MQTT] 断开，尝试重连...");
        mqttConnect();
    }
}

// ==================== 获取 MQTT 连接状态 ====================
inline bool mqttIsConnected() {
    return mqttClient.connected();
}

#endif // MQTT_MANAGER_H
