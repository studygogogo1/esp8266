#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP8266HTTPClient.h>
#include <bearssl/bearssl_hash.h>
#include <bearssl/bearssl_hmac.h>
#include "config.h"
#include "oled_display.h"
#include "pump_controller.h"

// ==================== 全局 MQTT 对象声明 ====================
extern WiFiClient espClient;
extern PubSubClient mqttClient;

// ==================== HTTP 获取时间戳（不走 UDP 123 端口，避免被路由器拦截）====================
// 获取 UTC 时间戳字符串，格式: YYYYMMDDHH（华为云 clientId 需要）
inline String ntpGetTimestamp() {
    WiFiClient client;

    // 方式1: 淘宝时间服务
    const char* host = "api.m.taobao.com";
    const char* path = "/rest/api3.do?api=mtop.common.getTimestamp";
    Serial.print("[NTP] 尝试淘宝时间服务...");
    if (client.connect(host, 80)) {
        client.print(String("GET ") + path + " HTTP/1.1\r\n" +
                     "Host: " + host + "\r\n" +
                     "Connection: close\r\n\r\n");
        int timeout = 0;
        while (!client.available() && timeout < 20) { delay(100); timeout++; }
        if (client.available()) {
            String line;
            while (client.available()) {
                line = client.readStringUntil('\n');
                if (line.indexOf("\"data\"") >= 0) {
                    int pos = line.indexOf("\"data\"");
                    String numStr = line.substring(pos + 7);
                    int end2 = 0;
                    while (end2 < numStr.length() && (numStr[end2] >= '0' && numStr[end2] <= '9')) end2++;
                    unsigned long ms = strtoul(numStr.substring(0, end2).c_str(), NULL, 10);
                    unsigned long unixTime = ms / 1000UL;

                    struct tm* tm_info = gmtime((time_t*)&unixTime);
                    char ts[11];
                    snprintf(ts, sizeof(ts), "%04d%02d%02d%02d",
                             tm_info->tm_year + 1900, tm_info->tm_mon + 1,
                             tm_info->tm_mday, tm_info->tm_hour);

                    Serial.print("成功! UTC时间戳: ");
                    Serial.println(ts);
                    client.stop();
                    return String(ts);
                }
            }
        }
        Serial.println("失败(无data字段)");
        client.stop();
    } else {
        Serial.println("失败(连接超时)");
    }

    // 方式2: 从 HTTP 响应头获取 Date
    Serial.print("[NTP] 尝试从HTTP Date头获取...");
    if (client.connect("www.baidu.com", 80)) {
        client.print("GET / HTTP/1.1\r\nHost: www.baidu.com\r\nConnection: close\r\n\r\n");
        int timeout = 0;
        while (!client.available() && timeout < 20) { delay(100); timeout++; }
        while (client.available()) {
            String line = client.readStringUntil('\n');
            if (line.startsWith("Date:")) {
                const char* months[] = {"Jan","Feb","Mar","Apr","May","Jun",
                                        "Jul","Aug","Sep","Oct","Nov","Dec"};
                int d = line.indexOf(",") + 2;
                while (line[d] == ' ') d++;
                int dd = 0;
                while (line[d] >= '0' && line[d] <= '9') { dd = dd * 10 + (line[d] - '0'); d++; }
                d++;
                String mon = line.substring(d, d + 3);
                d += 4;
                int yy = 0;
                while (d < line.length() && line[d] >= '0' && line[d] <= '9') { yy = yy * 10 + (line[d] - '0'); d++; }
                d++;
                int hh = 0;
                while (d < line.length() && line[d] >= '0' && line[d] <= '9') { hh = hh * 10 + (line[d] - '0'); d++; }
                int mm = 0;
                for (int i = 0; i < 12; i++) { if (mon == months[i]) { mm = i + 1; break; } }

                char ts[11];
                snprintf(ts, sizeof(ts), "%04d%02d%02d%02d", yy, mm, dd, hh);
                Serial.print("成功! UTC时间戳: ");
                Serial.println(ts);
                client.stop();
                return String(ts);
            }
        }
        Serial.println("失败(无Date头)");
        client.stop();
    }

    Serial.println("[NTP] 所有时间源均失败");
    return "";
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
