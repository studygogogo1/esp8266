#ifndef CONFIG_H
#define CONFIG_H

// ==================== 模式配置 ====================
// 设为 1: 模拟模式（不接硬件，用假数据测试 MQTT 通信）
// 设为 0: 正式模式（需要接传感器、继电器等硬件）
#define SIMULATION_MODE      1

// ==================== WiFi 配置 ====================
#define WIFI_SSID       "TP-LINK_3F59"
#define WIFI_PASSWORD   "cyy15757175753"

// ==================== 华为云 IoTDA MQTT 配置 ====================
// MQTT 接入地址（设备侧）
#define MQTT_HOST       "923924d24d.st1.iotda-device.cn-east-3.myhuaweicloud.com"
#define MQTT_PORT       8883    // MQTTS 加密端口（TLS）

// 设备信息（华为云控制台 → 设备详情页获取）
#define DEVICE_ID       "6a17a638e094d61592419546_00001"

// MQTT 认证信息（华为云控制台生成的，绑定时间戳，会过期）
// 如果你有设备密钥(DEVICE_SECRET)，代码会动态生成 clientId/password
// 如果没有，就用下面预生成的值（注意：会过期！）
#define MQTT_USERNAME   "6a17a638e094d61592419546_00001"
#define MQTT_PASSWORD   "c45d75f6216842a052a5c8f38408195d0a5f0e6fcab40c291390f45b7ec5dfeb"
#define MQTT_CLIENTID   "6a17a638e094d61592419546_00001_0_0_2026052814"

// 设备密钥（动态生成密码时需要，从华为云设备详情页复制）
// 如果填了，代码会忽略上面的预生成密码，自动用密钥动态计算
// 填入密钥后，把下面的 USE_DYNAMIC_PASSWORD 改为 1
#define DEVICE_SECRET   ""
#define USE_DYNAMIC_PASSWORD  0  // 1=用密钥动态生成密码, 0=用预生成密码

// ==================== 引脚定义 ====================
#if !SIMULATION_MODE
#define DHT11_PIN       D4      // GPIO2  - 温湿度传感器数据线
#define PUMP_PIN        D1      // GPIO5  - 继电器控制信号（LOW=吸合）
#define SOIL_PIN        A0      // ADC0   - 土壤湿度模拟输入
#define OLED_SDA        D2      // GPIO4  - OLED I2C 数据线
#define OLED_SCL        D3      // GPIO0  - OLED I2C 时钟线
#endif

// ==================== 系统参数 ====================
#define REPORT_INTERVAL     10000   // 数据上报间隔 10秒
#define PUMP_MAX_RUNTIME    30000   // 水泵最长运行 30秒
#define MQTT_RECONNECT_MS   5000    // MQTT 重连间隔 5秒
#define WIFI_RECONNECT_MS   30000   // WiFi 断开重连间隔 30秒
#define NTP_OFFSET          28800   // UTC+8 = 8*3600秒

// ==================== 华为云 MQTT Topic ====================
// 上报数据 Topic（→ 规则引擎 → HTTP 转发 → 自建服务器）
#define TOPIC_MSG_UP       "$oc/devices/6a17a638e094d61592419546_00001/sys/messages/up"
// 订阅命令 Topic（接收云端下发的控制指令）
#define TOPIC_CMD_SUB      "$oc/devices/6a17a638e094d61592419546_00001/sys/commands/#"
// 命令响应 Topic 前缀（回复到 commands/response/request_id=xxx，不会触发 messages/up 规则）
#define TOPIC_CMD_RESP     "$oc/devices/6a17a638e094d61592419546_00001/sys/commands/response/request_id="

// ==================== 固件版本 ====================
#define FIRMWARE_VERSION    "1.0.0"

#endif // CONFIG_H
