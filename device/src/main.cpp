/*
 * ESP8266 IoT 自动浇水系统 - 主程序
 *
 * SIMULATION_MODE=1: 不接硬件，用模拟数据测试 MQTT 通信链路
 * SIMULATION_MODE=0: 正式模式，连接 DHT11/土壤湿度/继电器/OLED
 *
 * 开发环境: VS Code + PlatformIO
 * 开发板:   NodeMCU 1.0 (ESP-12E)
 */

#include "config.h"

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <WiFiClient.h>
#include <ESP8266HTTPClient.h>
#include <time.h>
#include <sys/time.h>

#if !SIMULATION_MODE
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "oled_display.h"
#include "sensor_reader.h"
#include "pump_controller.h"
#endif

// ============================================================
//                     全局对象定义
// ============================================================

// TLS 加密客户端（8883 端口需要 SSL）
// 注意：1883端口用普通 WiFiClient 即可
#if MQTT_PORT == 8883
WiFiClientSecure espClient;
#else
WiFiClient espClient;
#endif
PubSubClient mqttClient(espClient);

// 华为云 MQTT 需要较大的 buffer（clientId + 密码都较长）
#define MQTT_BUFFER_SIZE 512

#if !SIMULATION_MODE
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
DHT dht(DHT11_PIN, DHT11);
#endif

// 模拟模式下的泵状态跟踪（正式模式用 pump_controller.h 的 pumpIsOn()）
#if SIMULATION_MODE
static bool simPumpOn = false;
#endif

inline bool getPumpStatus() {
#if SIMULATION_MODE
    return simPumpOn;
#else
    return pumpIsOn();
#endif
}

// ============================================================
//                     模拟数据生成（模拟模式用）
// ============================================================
#if SIMULATION_MODE

inline float simTemperature(unsigned long t) {
    return 25.0 + 5.0 * sin((float)t / 30000.0);
}
inline float simHumidity(unsigned long t) {
    return 60.0 + 15.0 * cos((float)t / 45000.0);
}
inline float simSoilMoisture(unsigned long t) {
    return 40.0 + 20.0 * sin((float)t / 60000.0);
}

#endif

// ============================================================
//       HTTP 获取 UTC 时间戳（淘宝/百度 HTTP，不走 UDP）
//       成功后自动设置系统时钟，供 event_time 使用
// ============================================================
static bool systemTimeSet = false;

// 用 Unix 时间戳设置 ESP8266 系统时钟
static void setSystemClock(unsigned long unixSeconds) {
    struct timeval tv;
    tv.tv_sec = (time_t)unixSeconds;
    tv.tv_usec = 0;
    settimeofday(&tv, NULL);
    systemTimeSet = true;
    Serial.print("[NTP] 系统时钟已设置: ");
    Serial.println(unixSeconds);
}

String ntpGetTimestamp() {
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
            int lineCount = 0;
            while (client.available()) {
                line = client.readStringUntil('\n');
                line.trim();
                lineCount++;
                if (line.length() > 0) {
                    Serial.print("[NTP] 行");
                    Serial.print(lineCount);
                    Serial.print(": ");
                    Serial.println(line);
                }
                if (line.indexOf("\"data\"") >= 0) {
                    int pos = line.indexOf("\"data\"");
                    String numStr = line.substring(pos + 7);
                    int end2 = 0;
                    while (end2 < (int)numStr.length() && (numStr[end2] >= '0' && numStr[end2] <= '9')) end2++;
                    // 淘宝返回毫秒时间戳（13位），32位 unsigned long 放不下
                    // 直接截取前10位作为秒级 Unix 时间戳
                    Serial.print("[NTP] 原始数字串(长度=");
                    Serial.print(end2);
                    Serial.print("): ");
                    Serial.println(numStr.substring(0, end2));
                    if (end2 > 10) end2 = 10;
                    unsigned long unixTime = strtoul(numStr.substring(0, end2).c_str(), NULL, 10);
                    Serial.print("[NTP] 解析Unix秒: ");
                    Serial.println(unixTime);

                    // 设置系统时钟，后续 event_time 直接用 time() 取
                    if (unixTime > 1700000000UL) {
                        setSystemClock(unixTime);
                    } else {
                        Serial.println("[NTP] Unix时间异常，不设置系统时钟");
                    }

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
                d++;  // skip space after year
                int hh = 0;
                while (d < line.length() && line[d] >= '0' && line[d] <= '9') { hh = hh * 10 + (line[d] - '0'); d++; }
                d++;  // skip ':'
                int min = 0;
                while (d < line.length() && line[d] >= '0' && line[d] <= '9') { min = min * 10 + (line[d] - '0'); d++; }
                d++;  // skip ':'
                int sec = 0;
                while (d < line.length() && line[d] >= '0' && line[d] <= '9') { sec = sec * 10 + (line[d] - '0'); d++; }

                int monthNum = 0;
                for (int i = 0; i < 12; i++) { if (mon == months[i]) { monthNum = i + 1; break; } }

                char ts[11];
                snprintf(ts, sizeof(ts), "%04d%02d%02d%02d", yy, monthNum, dd, hh);

                // 手动计算 Unix 时间戳（避免 mktime 的时区问题）
                int days = (yy - 1970) * 365 + (yy - 1969) / 4 - (yy - 1901) / 100 + (yy - 1601) / 400;
                int mdays[] = {31,28,31,30,31,30,31,31,30,31,30,31};
                if ((yy % 4 == 0 && yy % 100 != 0) || yy % 400 == 0) mdays[1] = 29;
                for (int i = 0; i < monthNum - 1; i++) days += mdays[i];
                days += dd - 1;
                unsigned long unixTime = (unsigned long)days * 86400UL
                                         + (unsigned long)hh * 3600UL
                                         + (unsigned long)min * 60UL
                                         + (unsigned long)sec;

                if (unixTime > 1700000000UL) {
                    setSystemClock(unixTime);
                }

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

// ============================================================
//        HMAC-SHA256 + Hex（仅 USE_DYNAMIC_PASSWORD=1 时编译）
//        华为云规则: Password = Hex(HMAC-SHA256(key=时间戳, data=密钥))
// ============================================================
#if USE_DYNAMIC_PASSWORD
#include <bearssl/bearssl_hash.h>
#include <bearssl/bearssl_hmac.h>

String generateMqttPassword(const String& timestamp) {
    // 华为云规则: Password = Hex(HMAC-SHA256(key=时间戳, data=设备密钥))
    br_hmac_key_context kc;
    br_hmac_key_init(&kc, &br_sha256_vtable,
                     timestamp.c_str(), timestamp.length());

    br_hmac_context ctx;
    br_hmac_init(&ctx, &kc, 0);
    br_hmac_update(&ctx, DEVICE_SECRET, strlen(DEVICE_SECRET));

    uint8_t hash[32];
    br_hmac_out(&ctx, hash);

    // 转为 Hex 字符串（华为云要的是 Hex，不是 Base64!）
    String result;
    result.reserve(64);
    const char hex[] = "0123456789abcdef";
    for (int i = 0; i < 32; i++) {
        result += hex[hash[i] >> 4];
        result += hex[hash[i] & 0x0F];
    }
    return result;
}
#endif // USE_DYNAMIC_PASSWORD

// ============================================================
//                     WiFi 连接管理
// ============================================================
bool wifiConnect() {
    Serial.println("[WiFi] 正在连接...");
    Serial.print("[WiFi] SSID: ");
    Serial.println(WIFI_SSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
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
    return false;
}

void wifiCheckReconnect(unsigned long now) {
    static unsigned long lastCheck = 0;
    if (now - lastCheck < WIFI_RECONNECT_MS) return;
    lastCheck = now;
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[WiFi] 断开，尝试重连...");
        wifiConnect();
    }
}

// ============================================================
//                     MQTT 连接（支持 TLS 8883）
// ============================================================
bool mqttConnect() {
    String useClientId = MQTT_CLIENTID;
    String useUsername = MQTT_USERNAME;
    String usePassword = MQTT_PASSWORD;

    // 如果配置了 DEVICE_SECRET，动态生成密码（长期有效）
#if USE_DYNAMIC_PASSWORD
    Serial.println("[MQTT] 使用设备密钥动态生成认证信息...");
    String timestamp = ntpGetTimestamp();
    if (timestamp.length() == 0) {
        Serial.println("[MQTT] NTP 失败，无法动态生成密码");
        return false;
    }
    useClientId = String(DEVICE_ID) + "_0_0_" + timestamp;
    usePassword = generateMqttPassword(timestamp);
#else
    Serial.println("[MQTT] 使用预生成认证信息（注意：会过期！）");
#endif

    Serial.println("[MQTT] 正在连接华为云 IoTDA...");
    Serial.print("[MQTT] Host: ");
    Serial.print(MQTT_HOST);
    Serial.print(":");
    Serial.println(MQTT_PORT);
    Serial.print("[MQTT] ClientID: ");
    Serial.println(useClientId);
    Serial.print("[MQTT] Username: ");
    Serial.println(useUsername);

    // 设置连接
#if MQTT_PORT == 8883
    espClient.setInsecure();  // 跳过证书验证
#endif
    mqttClient.setServer(MQTT_HOST, MQTT_PORT);
    mqttClient.setBufferSize(MQTT_BUFFER_SIZE);
    mqttClient.setKeepAlive(60);
    mqttClient.setSocketTimeout(15);

    Serial.print("[MQTT] ClientID 长度: ");
    Serial.println(useClientId.length());
    Serial.print("[MQTT] Password 长度: ");
    Serial.println(usePassword.length());
    Serial.print("[MQTT] Buffer 大小: ");
    Serial.println(MQTT_BUFFER_SIZE);

    bool connected = mqttClient.connect(
        useClientId.c_str(),
        useUsername.c_str(),
        usePassword.c_str()
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

    // 状态码含义:
    // -4: 连接超时
    // -2: 网络断开
    // -1: 连接失败（TLS握手失败/密码错误/服务器拒绝）
    //  1: 协议错误
    //  2: 客户端ID错误
    //  3: 服务器不可用
    //  4: 用户名/密码错误
    //  5: 未授权

    return false;
}

// 前向声明（mqttCallback 中需要调用 mqttReportData）
void mqttReportData(float temp, float humi, float soil, bool pumpOn, int rssi);

// MQTT 命令回调
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char msg[256];
    if (length >= sizeof(msg)) length = sizeof(msg) - 1;
    memcpy(msg, payload, length);
    msg[length] = '\0';

    Serial.println("========================================");
    Serial.print("[CMD] 收到命令 [");
    Serial.print(topic);
    Serial.println("]");
    Serial.print("[CMD] Payload: ");
    Serial.println(msg);

    // 从 Topic 中提取 request_id
    // Topic 格式: $oc/devices/{id}/sys/commands/request_id={request_id}
    String requestId = "";
    const char* reqPos = strstr(topic, "request_id=");
    if (reqPos) {
        requestId = String(reqPos + strlen("request_id="));
        Serial.print("[CMD] request_id: ");
        Serial.println(requestId);
    }

    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, msg)) {
        Serial.println("[CMD] JSON 解析失败");
        Serial.println("========================================");
        return;
    }

    // ======== 方式1: 华为云标准命令格式（与 Python 一致）========
    // {"service_id": "openWater", "command_name": "openWater", "paras": {"time": 3}}
    const char* serviceId   = doc["service_id"] | "";
    const char* commandName = doc["command_name"] | "";
    JsonObject paras       = doc["paras"] | JsonObject();

    if (strcmp(serviceId, "openWater") == 0) {
        int pumpTime = paras["time"] | 0;

#if !SIMULATION_MODE
        if (pumpTime > 0) {
            pumpOn(pumpTime);
            Serial.print("[CMD] 执行: 开泵 ");
            Serial.print(pumpTime);
            Serial.println(" 秒");
        } else {
            pumpOff();
            Serial.println("[CMD] 执行: 关泵");
        }
#else
        simPumpOn = (pumpTime > 0);
        if (pumpTime > 0) {
            Serial.print("[SIM] 开泵 ");
            Serial.print(pumpTime);
            Serial.println(" 秒");
        } else {
            Serial.println("[SIM] 关泵");
        }
#endif

        // 回复执行结果到 commands/response（不会触发 messages/up 规则引擎转发）
        String respTopic = TOPIC_CMD_RESP + requestId;
        StaticJsonDocument<128> resp;
        resp["result_code"] = 0;
        resp["response_name"] = "COMMAND_RESPONSE";
        JsonObject respParas = resp.createNestedObject("paras");
        respParas["result"] = "success";
        char buf[128];
        serializeJson(resp, buf);
        mqttClient.publish(respTopic.c_str(), buf);
        Serial.print("[CMD] 回复 -> ");
        Serial.print(respTopic);
        Serial.print(": ");
        Serial.println(buf);

        // 泵状态变化，立即上报最新状态（与 Python 回调一致）
        {
            unsigned long t = millis();
            float t2 = simTemperature(t), h2 = simHumidity(t), s2 = simSoilMoisture(t);
            mqttReportData(t2, h2, s2, getPumpStatus(), WiFi.RSSI());
        }

    // ======== 方式2: 自定义格式兼容 {"pump": "on", "duration": 30} ========
    } else if (doc.containsKey("pump")) {
        const char* cmd = doc["pump"];
        int dur = doc["duration"] | 30;

#if !SIMULATION_MODE
        if (strcmp(cmd, "on") == 0) {
            pumpOn(dur);
            Serial.print("[CMD] 执行(pump): 开泵 ");
            Serial.print(dur);
            Serial.println(" 秒");
        } else if (strcmp(cmd, "off") == 0) {
            pumpOff();
            Serial.println("[CMD] 执行(pump): 关泵");
        }
#else
        simPumpOn = (strcmp(cmd, "on") == 0);
        Serial.print("[SIM] pump命令: ");
        Serial.println(cmd);
#endif

        String respTopic = TOPIC_CMD_RESP + requestId;
        StaticJsonDocument<128> resp;
        resp["result_code"] = 0;
        resp["response_name"] = "COMMAND_RESPONSE";
        JsonObject respParas = resp.createNestedObject("paras");
        respParas["result"] = "success";
        char buf[128];
        serializeJson(resp, buf);
        mqttClient.publish(respTopic.c_str(), buf);
        Serial.print("[CMD] 回复 -> ");
        Serial.print(respTopic);
        Serial.print(": ");
        Serial.println(buf);

        // 泵状态变化，立即上报最新状态
        {
            unsigned long t = millis();
            float t2 = simTemperature(t), h2 = simHumidity(t), s2 = simSoilMoisture(t);
            mqttReportData(t2, h2, s2, getPumpStatus(), WiFi.RSSI());
        }

    } else {
        Serial.print("[CMD] 未知命令, service_id=");
        Serial.print(serviceId);
        Serial.print(", command_name=");
        Serial.println(commandName);
    }

    Serial.println("========================================");
}

// 上报传感器数据到华为云
void mqttReportData(float temp, float humi, float soil, bool pumpOn, int rssi) {
    StaticJsonDocument<512> doc;
    JsonArray servicesArr = doc.createNestedArray("services");
    JsonObject svc = servicesArr.createNestedObject();
    svc["service_id"] = "sensor_data";
    JsonObject props = svc.createNestedObject("properties");
    props["temperature"] = temp;
    props["humidity"] = humi;
    props["soil_moisture"] = soil;
    props["pump_status"] = pumpOn;
    props["wifi_signal"] = rssi;
    props["firmware_version"] = FIRMWARE_VERSION;

    // event_time: ISO 8601 北京时间（UTC+8），末尾不带 Z
    if (systemTimeSet && time(nullptr) > 1700000000L) {
        time_t now = time(nullptr) + 8 * 3600;  // UTC+8
        struct tm* bj = gmtime(&now);
        char eventTime[28];
        snprintf(eventTime, sizeof(eventTime),
                 "%04d-%02d-%02dT%02d:%02d:%02d",
                 bj->tm_year + 1900, bj->tm_mon + 1, bj->tm_mday,
                 bj->tm_hour, bj->tm_min, bj->tm_sec);
        svc["event_time"] = eventTime;
        Serial.print("[REPORT] event_time: ");
        Serial.println(eventTime);
    } else {
        Serial.println("[REPORT] 系统时钟未同步，跳过 event_time");
    }

    char buf[512];
    serializeJson(doc, buf);

    Serial.println("========================================");
    Serial.print("[REPORT] -> ");
    Serial.println(TOPIC_MSG_UP);
    Serial.print("[REPORT] ");
    Serial.println(buf);

    if (mqttClient.publish(TOPIC_MSG_UP, buf)) {
        Serial.println("[REPORT] 上报成功!");
    } else {
        Serial.println("[REPORT] 上报失败!");
    }
    Serial.println("========================================");
}

void mqttCheckConnection(unsigned long now) {
    static unsigned long lastCheck = 0;
    if (now - lastCheck < MQTT_RECONNECT_MS) return;
    lastCheck = now;
    if (!mqttClient.connected()) {
        Serial.println("[MQTT] 断开，尝试重连...");
        mqttConnect();
    }
}

// ============================================================
//                     setup()
// ============================================================
void setup() {
    Serial.begin(115200);
    Serial.println();
    Serial.println("========================================");
    Serial.println("  ESP8266 IoT v" FIRMWARE_VERSION);
#if SIMULATION_MODE
    Serial.println("  *** 模拟模式 - 不连接硬件 ***");
#else
    Serial.println("  *** 正式模式 ***");
#endif
    Serial.println("========================================");

    // 硬件初始化（仅正式模式）
#if !SIMULATION_MODE
    oledBegin();
    oledShowSplash("ESP8266 IoT", "Starting...");
    pumpBegin();
    sensorBegin();
#endif

    // WiFi 连接
    Serial.println("[SETUP] 连接 WiFi...");
    if (!wifiConnect()) {
        Serial.println("[ERROR] WiFi 失败，5秒后重启");
        delay(5000);
        ESP.restart();
    }

    // MQTT 连接
    Serial.println("[SETUP] 连接华为云 MQTT...");
    mqttClient.setCallback(mqttCallback);
    if (!mqttConnect()) {
        Serial.println("[WARN] MQTT 首次失败，loop 中重试");
    }

    Serial.println("========================================");
    Serial.println("  启动完成! 每10秒上报一次数据");
    Serial.println("========================================");
}

// ============================================================
//                     loop()
// ============================================================
void loop() {
    unsigned long now = millis();

    wifiCheckReconnect(now);
    mqttCheckConnection(now);

#if !SIMULATION_MODE
    pumpCheckTimeout(now);
#endif

    static unsigned long lastReport = 0;
    if (now - lastReport >= REPORT_INTERVAL) {
        lastReport = now;

        float temp, humi, soil;

#if SIMULATION_MODE
        temp = simTemperature(now);
        humi = simHumidity(now);
        soil = simSoilMoisture(now);
        Serial.println("--- 模拟数据 ---");
        Serial.print("  T:"); Serial.print(temp,1); Serial.print("C  H:"); Serial.print(humi,0); Serial.print("%  Soil:"); Serial.print(soil,0); Serial.println("%");
#else
        SensorData data = readSensors();
        temp = data.temperature;
        humi = data.humidity;
        soil = data.soilMoisture;
        oledShowDashboard(temp, humi, soil, pumpIsOn(), WiFi.RSSI(), mqttClient.connected());
#endif

        if (mqttClient.connected()) {
            mqttReportData(temp, humi, soil, getPumpStatus(), WiFi.RSSI());
        } else {
            Serial.println("[LOOP] MQTT 未连接，跳过上报");
        }
    }

    if (mqttClient.connected()) {
        mqttClient.loop();
    }
}
