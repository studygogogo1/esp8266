# ESP8266 设备端开发说明

> 本文档供在**连接开发板的电脑**上开发 ESP8266 代码时参考。
> 配套的服务器端和 App 端代码已在 `../server/` 和 `../app/` 中完成。

---

## 一、硬件配置

| 硬件 | 型号 | 数量 |
|------|------|------|
| 开发板 | NodeMCU (ESP-12E) | 1 |
| 温湿度传感器 | DHT11 | 1 |
| 土壤湿度传感器 | 模拟量输出型 | 1 |
| 继电器模块 | 低电平触发型 | 1 |
| OLED 显示屏 | SSD1306 (128x64, I2C) | 1 |

---

## 二、引脚接线

| 外设 | 外设引脚 | NodeMCU 引脚 | GPIO 编号 | 说明 |
|------|---------|-------------|----------|------|
| **DHT11** | DATA | D4 | GPIO2 | 温湿度传感器数据线 |
| | VCC | 3.3V | — | 电源正极 |
| | GND | GND | — | 电源负极 |
| **土壤湿度** | AO | A0 | ADC0 | 模拟量输出（0-3.3V） |
| | VCC | 3.3V | — | 电源正极 |
| | GND | GND | — | 电源负极 |
| **继电器** | IN | D1 | GPIO5 | 控制信号（LOW=吸合） |
| | VCC | 3.3V | — | 电源正极 |
| | GND | GND | — | 电源负极 |
| **OLED** | SDA | D2 | GPIO4 | I2C 数据线 |
| | SCL | D3 | GPIO0 | I2C 时钟线 |
| | VCC | 3.3V | — | 电源正极 |
| | GND | GND | — | 电源负极 |

### 接线示意图（文字版）

```
NodeMCU                          外设
+------------------+
|                  |           +--------+
|    3.3V  --------+-----------+ VCC    |  DHT11
|     GND  --------+-----------+ GND    |
|     D4   --------+-----------+ DATA   |
|                  |           +--------+
|    3.3V  --------+-----------+ VCC    |  土壤湿度
|     GND  --------+-----------+ GND    |
|     A0   --------+-----------+ AO     |
|                  |           +--------+
|    3.3V  --------+-----------+ VCC    |  继电器
|     GND  --------+-----------+ GND    |
|     D1   --------+-----------+ IN     |
|                  |           +--------+
|    3.3V  --------+-----------+ VCC    |  OLED
|     GND  --------+-----------+ GND    |
|     D2   --------+-----------+ SDA    |
|     D3   --------+-----------+ SCL    |
|                  |           +--------+
+------------------+
```

### 继电器接线（控制水泵）

```
继电器常开触点
  COM  ----- 水泵电源正极
  NO   ----- 水泵正极
  水泵负极 ---- 水泵电源负极

⚠️ 安全提醒：
  - 继电器控制的是 220V 交流电，接线时务必断电
  - 建议用 5V 小水泵 + 独立电源，避免 220V 风险
```

---

## 三、开发环境

### Arduino IDE 配置

| 配置项 | 值 |
|--------|-----|
| 开发板 | NodeMCU 1.0 (ESP-12E Module) |
| 上传速率 | 115200 |
| Flash Size | 4MB (FS:2MB OTA:~1019KB) |

### 需要安装的库（Arduino 库管理器搜索安装）

| 库名 | 用途 | 版本 |
|------|------|------|
| **PubSubClient** | MQTT 客户端 | 最新版 |
| **DHT sensor library** | DHT11 温湿度读取 | 最新版 |
| **Adafruit SSD1306** | OLED 显示屏驱动 | 最新版 |
| **Adafruit GFX Library** | OLED 图形库 | 最新版 |
| **ArduinoJson** | JSON 编解码 | 6.x 版本 |
| **NTPClient** | 网络时间同步 | 最新版 |

---

## 四、华为云 IoTDA MQTT 连接参数

### 设备信息（从华为云控制台获取）

| 参数 | 说明 | 获取位置 |
|------|------|---------|
| **设备 ID** | `6a17a638e094d61592419546_xxxxx` | 控制台 → 设备 → 设备详情 |
| **产品 ID** | 产品唯一标识 | 控制台 → 产品 → 产品详情 |
| **MQTT 接入地址** | 设备侧接入域名 | 控制台 → 总览 → 平台接入地址 → 设备侧 |
| **MQTT 端口** | `1883` | 非加密端口 |
| **设备密钥** | 设备注册时设置的密钥 | 设备详情页 |

### MQTT 连接参数

```
Client ID: {设备ID}_0_0_2026052801
Username:  {产品ID}
Password:  hmac_sha256({设备密钥}, {时间戳})
           （华为云会提供"生成工具"，在控制台直接生成）
```

### MQTT Topic 说明

| Topic | 方向 | 用途 |
|-------|------|------|
| `$oc/devices/{device_id}/sys/properties/report` | 设备→云 | 上报属性数据 |
| `$oc/devices/{device_id}/sys/messages/down` | 云→设备 | 接收下发消息（命令） |
| `$oc/devices/{device_id}/sys/messages/up` | 设备→云 | 上报消息 |
| `$oc/devices/{device_id}/sys/gateway/sub_devices` | 设备→云 | 子设备上报（暂不使用） |

---

## 五、数据通信协议

### 5.1 设备上报数据（设备 → 华为云 → 服务器）

**上报 Topic：** `$oc/devices/{device_id}/sys/properties/report`

**上报频率：** 每 10 秒上报一次

**JSON 格式：**

```json
{
  "services": [{
    "service_id": "sensor",
    "properties": {
      "temperature": 28.5,
      "humidity": 65.0,
      "soil_moisture": 25.0,
      "pump_status": false,
      "wifi_signal": -65,
      "firmware_version": "1.0.0"
    }
  }]
}
```

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| temperature | float | -20~60 | 温度（℃） |
| humidity | float | 0~100 | 空气湿度（%） |
| soil_moisture | float | 0~100 | 土壤湿度（%，0=最干，100=最湿） |
| pump_status | bool | true/false | 水泵当前状态 |
| wifi_signal | int | -100~0 | WiFi 信号强度（dBm） |
| firmware_version | string | — | 固件版本号 |

### 5.2 服务器下发命令（服务器 → 华为云 → 设备）

**接收 Topic：** `$oc/devices/{device_id}/sys/messages/down`

**JSON 格式：**

```json
{
  "pump": "on"
}
```

或

```json
{
  "pump": "off"
}
```

### 5.3 命令执行响应（设备 → 华为云 → 服务器）

**上报 Topic：** `$oc/devices/{device_id}/sys/messages/up`

```json
{
  "command": "pump",
  "status": "success",
  "timestamp": "2026-05-28T20:30:00"
}
```

---

## 六、代码框架说明

### 文件结构（在 `device/` 目录下创建）

```
device/
├── esp8266_iot.ino          # 主程序
├── config.h                  # 配置（WiFi、MQTT、引脚）
├── wifi_manager.h            # WiFi 连接管理
├── mqtt_manager.h            # MQTT 连接和消息处理
├── sensor_reader.h           # 传感器数据读取（DHT11 + 土壤湿度）
├── pump_controller.h         # 水泵/继电器控制
├── oled_display.h            # OLED 屏幕显示
└── README.md                 # 本文档
```

### 主程序流程（`esp8266_iot.ino`）

```
setup():
  1. 初始化串口（115200）
  2. 初始化引脚（DHT11、继电器、OLED）
  3. 连接 WiFi（显示进度到 OLED）
  4. 初始化 NTP 时间同步
  5. 连接华为云 MQTT
  6. 订阅命令 Topic

loop():
  1. 检查 MQTT 连接，断开则重连
  2. 每 10 秒读取一次传感器数据
  3. 组装 JSON 并上报到华为云
  4. 更新 OLED 显示
  5. 处理 MQTT 消息（命令）
```

### 关键逻辑说明

#### 1. 土壤湿度百分比计算

土壤湿度传感器输出的是 0-3.3V 的模拟电压，对应 ADC 读数 0-1023。

```cpp
// 读取原始值
int raw = analogRead(A0);
// 转换为百分比（0% = 最干, 100% = 最湿）
// 注意：土壤湿度传感器在空气中输出最大（约1023），在水中输出最小（约300）
// 所以需要反向映射
float moisture = map(raw, 1023, 300, 0, 100);
moisture = constrain(moisture, 0, 100);
```

#### 2. 水泵控制逻辑

```cpp
// 开水泵（低电平触发）
digitalWrite(PUMP_PIN, LOW);
// 关水泵
digitalWrite(PUMP_PIN, HIGH);
```

**安全机制：** 无论手动还是自动，每次开水泵最多运行 30 秒后自动关闭，防止长时间空转。

#### 3. MQTT 消息接收

```cpp
void callback(char* topic, byte* payload, unsigned int length) {
    // 1. 将 payload 转为字符串
    // 2. 用 ArduinoJson 解析 JSON
    // 3. 检查是否包含 "pump" 字段
    // 4. 如果 pump=="on" → 开水泵并计时
    // 5. 如果 pump=="off" → 关水泵
    // 6. 回复执行结果
}
```

#### 4. OLED 显示内容

```
┌──────────────────────┐
│  🌡 28.5℃  💧 65%   │  第1行：温度 + 空气湿度
│  🌱 土壤: 25%       │  第2行：土壤湿度
│  🚿 水泵: 关闭       │  第3行：水泵状态
│  📶 -65dBm  ✅在线  │  第4行：WiFi信号 + MQTT状态
└──────────────────────┘
```

---

## 七、华为云 IoTDA 配置步骤

### 7.1 创建产品

1. 登录华为云 IoTDA 控制台：https://console.huaweicloud.com/iotdm/
2. 进入实例 `e01941fb-c614-415f-98cb-5d776280d89a`
3. 左侧菜单 → 产品 → 创建产品
4. 填写：
   - 产品名称：`esp8266`
   - 协议：MQTT
   - 数据格式：JSON
   - 设备类型：自定义

### 7.2 定义产品模型（物模型）

在产品的"模型定义"中添加以下属性：

| 属性名 | 数据类型 | 取值范围 | 步长 | 单位 | 读写 |
|--------|---------|---------|------|------|------|
| temperature | decimal | -20~60 | 0.1 | ℃ | 只读 |
| humidity | decimal | 0~100 | 0.1 | % | 只读 |
| soil_moisture | decimal | 0~100 | 0.1 | % | 只读 |
| pump_status | boolean | — | — | — | 只读 |
| wifi_signal | int | -100~0 | 1 | dBm | 只读 |
| firmware_version | string | 0~64字节 | — | — | 只读 |

### 7.3 注册设备

1. 产品 → 设备 → 注册设备
2. 设备名称：`esp8266_01`（或自定义）
3. 设备标识码：使用 ESP8266 的 MAC 地址或自定义
4. 密钥：记录好，写入 ESP8266 代码的 `config.h`

### 7.4 配置规则引擎（数据转发到服务器）

1. 左侧菜单 → 规则 → 创建规则
2. 规则名称：`forward_to_server`
3. 触发事件：设备属性上报
4. 执行动作：HTTP 转发
   - URL：`http://{服务器IP}:8000/iot/data`
   - 方法：POST
   - 超时：5秒

---

## 八、config.h 配置模板

```cpp
// ========== WiFi 配置 ==========
#define WIFI_SSID     "你的WiFi名称"
#define WIFI_PASSWORD "你的WiFi密码"

// ========== 华为云 IoTDA MQTT 配置 ==========
#define MQTT_BROKER   "xxxxxxxxx.iot-mqtts.cn-east-3.myhuaweicloud.com"  // 设备侧 MQTT 地址
#define MQTT_PORT     1883
#define DEVICE_ID     "你的设备ID"
#define PRODUCT_ID    "你的产品ID"
#define DEVICE_SECRET "你的设备密钥"

// ========== 引脚定义 ==========
#define DHT11_PIN     2   // D4 → GPIO2
#define PUMP_PIN      5   // D1 → GPIO5
#define SOIL_PIN      A0  // 模拟输入
#define OLED_SDA      4   // D2 → GPIO4
#define OLED_SCL      0   // D3 → GPIO0

// ========== 系统参数 ==========
#define REPORT_INTERVAL    10000  // 数据上报间隔（毫秒）
#define PUMP_MAX_RUNTIME   30000  // 水泵最长运行时间（毫秒）
#define MQTT_RECONNECT     5000   // MQTT 重连间隔（毫秒）
```

---

## 九、快速上手步骤

1. **打开 Arduino IDE**，选择开发板：NodeMCU 1.0 (ESP-12E Module)
2. **安装所需库**（库管理器搜索安装，见第三节）
3. **复制 `config.h` 模板**，填入你的 WiFi 密码和华为云设备信息
4. **创建 `esp8266_iot.ino`**，编写主程序（参考第六节的流程）
5. **连接开发板**，选择正确的 COM 口
6. **编译上传**，打开串口监视器（115200 波特率）查看日志
7. **验证**：
   - OLED 是否正常显示
   - 串口是否打印 MQTT 连接成功
   - 华为云控制台是否收到设备上报数据
   - 服务器 `/iot/data` 是否收到转发数据

---

## 十、参考资源

| 资源 | 地址 |
|------|------|
| 华为云 IoTDA MQTT 接入文档 | https://support.huaweicloud.com/usermanual-iothub/iot_01_0010.html |
| MQTT 密码生成工具 | 华为云控制台 → 设备详情 → MQTT 接入信息 |
| PubSubClient 库文档 | https://pubsubclient.knolleary.net/ |
| ArduinoJson 文档 | https://arduinojson.org/v6/doc/ |
| NodeMCU 引脚对照表 | https://randomnerdtutorials.com/esp8266-pinout-reference-gpios/ |
