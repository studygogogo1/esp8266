# ESP8266 IoT 控制平台

ESP8266 物联网远程控制系统，支持温湿度监测、水泵远程控制、自动浇水、历史数据查看。

## 项目结构

```
esp8266/
├── server/          # FastAPI 服务器端
│   ├── app/
│   │   ├── api/     # REST API 路由
│   │   ├── models/  # 数据库模型
│   │   ├── services/# 业务逻辑（华为云IoT、数据处理）
│   │   ├── core/    # 配置、数据库、WebSocket
│   │   └── main.py  # 应用入口
│   ├── firmware/    # OTA 固件文件目录
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
│
└── app/             # React Native Android App
    ├── src/
    │   ├── api/     # 服务器接口 + WebSocket
    │   ├── store/   # 全局状态管理
    │   ├── screens/ # 页面
    │   │   ├── DashboardScreen.tsx  # 实时仪表盘
    │   │   ├── HistoryScreen.tsx    # 历史曲线
    │   │   ├── AlertsScreen.tsx     # 告警配置
    │   │   └── PumpLogsScreen.tsx   # 浇水记录
    │   ├── config.ts
    │   └── App.tsx
    └── package.json
```

## 服务器端快速启动

### 1. 安装依赖

```bash
cd server
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写华为云 IoTDA 的 AK/SK/ProjectId/Endpoint
```

### 3. 启动服务器

```bash
python run.py
```

访问 http://localhost:8000/docs 查看 API 文档

---

## App 快速启动

### 1. 安装依赖

```bash
cd app
npm install
```

### 2. 修改服务器地址

编辑 `src/config.ts`，改为你服务器的实际 IP：

```ts
BASE_URL: 'http://你的服务器IP:8000',
WS_URL:  'ws://你的服务器IP:8000/ws',
```

### 3. 修改设备 ID

```ts
DEFAULT_DEVICE_ID: '华为云控制台里的设备ID',
```

### 4. 运行 App

```bash
# 连接 Android 手机（开启 USB 调试）
npx react-native run-android
```

---

## 华为云 IoTDA 配置

### 1. 创建产品

- 登录 https://console.huaweicloud.com
- 搜索"设备接入 IoTDA" → 开通
- 创建产品：协议选 **MQTT**，格式选 **JSON**

### 2. 注册设备

- 在产品下新增设备
- 记录：设备ID、设备密钥、接入域名

### 3. 配置规则引擎（数据转发到你的服务器）

- IoTDA 控制台 → 规则 → 数据转发
- 新建规则：触发器 = 设备上报数据
- 动作 = HTTP 转发到 `http://你的服务器IP:8000/api/iot/data`

---

## ESP8266 上报数据格式（MQTT Payload）

```json
{
  "temperature": 28.5,
  "humidity": 65.0,
  "soil_moisture": 25.0,
  "pump_status": false,
  "wifi_signal": -65,
  "firmware_version": "1.0.0"
}
```

## ESP8266 接收指令格式（服务器下发）

```json
{"pump": "on", "duration": 30}
{"pump": "off"}
```

---

## API 接口列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/devices/ | 设备列表 |
| GET | /api/devices/{id} | 设备详情 |
| POST | /api/devices/{id}/pump | 控制水泵 |
| GET | /api/sensor/{id}/history | 传感器历史数据 |
| GET | /api/sensor/{id}/stats | 统计数据 |
| GET | /api/pump/{id}/logs | 水泵操作记录 |
| GET | /api/alerts/{id}/list | 告警列表 |
| GET/POST | /api/alerts/{id}/rules | 告警规则配置 |
| GET/POST | /api/rules/{id} | 自动控制规则 |
| GET | /api/firmware/latest | OTA 最新版本查询 |
| GET | /api/firmware/download/{ver} | 固件下载 |
| POST | /api/iot/data | 华为云 IoTDA 数据推送（内部） |
| WS | /ws | WebSocket 实时数据推送 |
