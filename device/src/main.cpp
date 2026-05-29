/*
 * ESP8266 IoT 自动浇水系统 - 主程序
 *
 * SIMULATION_MODE=1: 不接硬件，用模拟数据测试 MQTT 通信链路
 * SIMULATION_MODE=0: 正式模式，连接 DHT11/土壤湿度/继电器
 *
 * 开发环境: VS Code + PlatformIO
 * 开发板:   NodeMCU 1.0 (ESP-12E)
 */

#include "config.h"

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <WiFiUdp.h>

#if !SIMULATION_MODE
#include <DHT.h>
#include "sensor_reader.h"
#include "pump_controller.h"
#endif

// ============================================================
//                     全局对象定义
// ============================================================

// TLS 加密客户端（8883 端口需要 SSL）
WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);

// 华为云 MQTT 需要较大的 buffer（clientId + 密码都较长）
#define MQTT_BUFFER_SIZE 512

#if !SIMULATION_MODE
DHT dht(DHT11_PIN, DHT11);
#endif

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
//                     NTP 时间同步（获取 YYYYMMDDHH 格式时间戳）
// ============================================================
String ntpGetTimestamp() {
    WiFiUDP ntpUDP;
    const char* ntpServer = "ntp.aliyun.com";
    const int ntpPort = 123;
    ntpUDP.begin(ntpPort);

    byte packet[48];
    memset(packet, 0, 48);
    packet[0] = 0b11100011;
    packet[1] = 0;
    packet[2] = 6;
    packet[3] = 0xEC;

    if (ntpUDP.beginPacket(ntpServer, ntpPort) != 1) {
        return "";
    }
    ntpUDP.write(packet, 48);
    ntpUDP.endPacket();

    int timeout = 0;
    while (ntpUDP.parsePacket() == 0 && timeout < 10) {
        delay(100);
        timeout++;
    }

    if (ntpUDP.parsePacket() == 0) {
        Serial.println("[NTP] 时间同步失败");
        return "";
    }

    ntpUDP.read(packet, 48);

    unsigned long highWord = word(packet[40], packet[41]);
    unsigned long lowWord  = word(packet[42], packet[43]);
    unsigned long secsSince1900 = highWord << 16 | lowWord;
    // 华为云需要 UTC 时间，不加时区偏移
    unsigned long unixTime = secsSince1900 - 2208988800UL;

    struct tm* tm_info = gmtime((time_t*)&unixTime);
    char ts[11];  // YYYYMMDDHH = 10位 + \0
    snprintf(ts, sizeof(ts), "%04d%02d%02d%02d",
             tm_info->tm_year + 1900, tm_info->tm_mon + 1, tm_info->tm_mday,
             tm_info->tm_hour);

    Serial.print("[NTP] UTC时间戳(YYYYMMDDHH): ");
    Serial.println(ts);
    return String(ts);
}

// ============================================================
//        HMAC-SHA256 + Hex（仅 USE_DYNAMIC_PASSWORD=1 时编译）
//        华为云规则: Password = Hex(HMAC-SHA256(key=设备密钥, msg=时间戳))
// ============================================================
#if USE_DYNAMIC_PASSWORD
#include <bearssl_hash.h>

void hmacSha256(const char* key, size_t keyLen,
                const char* msg, size_t msgLen, uint8_t* output) {
    br_sha256_context ctx;
    uint8_t k_prime[64];
    memset(k_prime, 0, 64);
    if (keyLen > 64) {
        br_sha256_init(&ctx); br_sha256_update(&ctx, (const uint8_t*)key, keyLen);
        uint8_t tmp[32]; br_sha256_out(&ctx, tmp); memcpy(k_prime, tmp, 32);
    } else {
        memcpy(k_prime, key, keyLen);
    }

    uint8_t inner[64 + 128];
    for (int i = 0; i < 64; i++) inner[i] = k_prime[i] ^ 0x36;
    memcpy(inner + 64, msg, msgLen);

    uint8_t innerHash[32];
    br_sha256_init(&ctx); br_sha256_update(&ctx, inner, 64 + msgLen); br_sha256_out(&ctx, innerHash);

    uint8_t outer[64 + 32];
    for (int i = 0; i < 64; i++) outer[i] = k_prime[i] ^ 0x5C;
    memcpy(outer + 64, innerHash, 32);

    br_sha256_init(&ctx); br_sha256_update(&ctx, outer, 96); br_sha256_out(&ctx, output);
}

// 转为 Hex 字符串（华为云要的是 Hex，不是 Base64!）
String hexEncode(const uint8_t* data, size_t len) {
    String result;
    result.reserve(len * 2);
    const char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        result += hex[data[i] >> 4];
        result += hex[data[i] & 0x0F];
    }
    return result;
}

String generateMqttPassword(const String& timestamp) {
    // 华为云规则: key=设备密钥, msg=UTC时间戳(YYYYMMDDHH)
    // 注意: 顺序必须是 密钥在前，时间戳在后！
    uint8_t hash[32];
    hmacSha256(DEVICE_SECRET, strlen(DEVICE_SECRET),
               timestamp.c_str(), timestamp.length(), hash);
    return hexEncode(hash, 32);
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

    // 设置 TLS 连接
    espClient.setInsecure();  // 跳过证书验证（测试阶段用，生产环境应加载CA证书）
    mqttClient.setServer(MQTT_HOST, MQTT_PORT);
    mqttClient.setBufferSize(MQTT_BUFFER_SIZE);

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

// MQTT 命令回调
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char msg[128];
    if (length >= sizeof(msg)) length = sizeof(msg) - 1;
    memcpy(msg, payload, length);
    msg[length] = '\0';

    Serial.print("[MQTT] 收到命令 [");
    Serial.print(topic);
    Serial.print("]: ");
    Serial.println(msg);

    // 从 Topic 中提取 request_id
    // Topic 格式: $oc/devices/{id}/sys/commands/request_id={request_id}
    String requestId = "";
    const char* reqPos = strstr(topic, "request_id=");
    if (reqPos) {
        requestId = String(reqPos + strlen("request_id="));
    }

    StaticJsonDocument<128> doc;
    if (deserializeJson(doc, msg)) {
        Serial.println("[MQTT] JSON 解析失败");
        return;
    }

    if (doc.containsKey("pump")) {
        const char* cmd = doc["pump"];
        const char* result = "success";

#if !SIMULATION_MODE
        if (strcmp(cmd, "on") == 0) {
            int dur = doc["duration"] | 30;
            pumpOn(dur);
        } else if (strcmp(cmd, "off") == 0) {
            pumpOff();
        }
#else
        Serial.print("[SIM] 水泵命令: ");
        Serial.println(cmd);
#endif

        // 回复执行结果到 commands/response（不会触发 messages/up 规则引擎转发）
        String respTopic = TOPIC_CMD_RESP + requestId;
        StaticJsonDocument<128> resp;
        resp["result_code"] = 0;
        resp["response_name"] = "COMMAND_RESPONSE";
        JsonObject respParas = resp.createNestedObject("paras");
        respParas["result"] = result;
        char buf[128];
        serializeJson(resp, buf);
        mqttClient.publish(respTopic.c_str(), buf);
        Serial.print("[MQTT] 已回复 ");
        Serial.print(respTopic);
        Serial.print(": ");
        Serial.println(buf);
    }
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

    char buf[512];
    serializeJson(doc, buf);

    Serial.println("[MQTT] 上报数据:");
    Serial.println(buf);

    if (mqttClient.publish(TOPIC_MSG_UP, buf)) {
        Serial.println("[MQTT] 上报成功!");
    } else {
        Serial.println("[MQTT] 上报失败!");
    }
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
        bool pumpOn;

#if SIMULATION_MODE
        temp = simTemperature(now);
        humi = simHumidity(now);
        soil = simSoilMoisture(now);
        pumpOn = false;  // 模拟模式无真实水泵，命令处理在 mqttCallback 中打印日志
        Serial.println("--- 模拟数据 ---");
        Serial.print("  T:"); Serial.print(temp,1); Serial.print("C  H:"); Serial.print(humi,0); Serial.print("%  Soil:"); Serial.print(soil,0); Serial.println("%");
#else
        SensorData data = readSensors();
        temp = data.temperature;
        humi = data.humidity;
        soil = data.soilMoisture;
        pumpOn = pumpIsOn();
        Serial.print("[Sensor] T:"); Serial.print(temp,1); Serial.print("C  H:"); Serial.print(humi,0); Serial.print("%  Soil:"); Serial.print(soil,0); Serial.print("%  Pump:"); Serial.println(pumpOn ? "ON" : "OFF");
#endif

        if (mqttClient.connected()) {
            mqttReportData(temp, humi, soil, pumpOn, WiFi.RSSI());
        } else {
            Serial.println("[LOOP] MQTT 未连接，跳过上报");
        }
    }

    if (mqttClient.connected()) {
        mqttClient.loop();
    }
}
