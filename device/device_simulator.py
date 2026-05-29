"""
ESP8266 设备模拟器
功能：
1. 模拟设备连接华为云 IoTDA（MQTT）
2. 定时上报模拟的传感器数据（温度、湿度、土壤湿度等）
3. 订阅云端指令 Topic，接收并解析控制命令
4. 模拟执行指令（含自动关泵定时器），并上报执行结果
5. 自动重连、动态密码更新

使用方法：
  python device_simulator.py                # 使用动态密码（默认）
  python device_simulator.py --mode pregen # 使用预生成密码
  python device_simulator.py --log         # 启用日志记录
"""

import argparse
import hashlib
import hmac
import json
import logging
import os
import random
import ssl
import sys
import threading
import time
import datetime
import paho.mqtt.client as mqtt

# ============================================================
#                    配置区（与 ESP8266 保持一致）
# ============================================================
DEVICE_ID      = "6a17a638e094d61592419546_00001"
DEVICE_SECRET  = "Cyy542100312"

MQTT_HOST      = "923924d24d.st1.iotda-device.cn-east-3.myhuaweicloud.com"
MQTT_PORT      = 1883                        # 非 TLS（与 ESP8266 当前配置一致）

# 上报 Topic（设备 → 华为云）
# 消息上报 → 规则引擎 → HTTP 转发 → 自建服务器
MESSAGE_TOPIC = f"$oc/devices/{DEVICE_ID}/sys/messages/up"

# 命令下发 Topic（华为云 → 设备）
SUBSCRIBE_TOPIC = f"$oc/devices/{DEVICE_ID}/sys/commands/#"

# 命令响应 Topic（设备 → 华为云）
RESPONSE_TOPIC = f"$oc/devices/{DEVICE_ID}/sys/commands/response"

# 模拟数据上报间隔（秒）
REPORT_INTERVAL = 10

# 动态密码更新间隔（秒）- 华为云令牌1小时过期，这里45分钟更新一次
PASSWORD_UPDATE_INTERVAL = 45 * 60

# ============================================================
#              动态密码生成（与 ESP8266 算法一致）
# ============================================================
def get_utc_timestamp_hour():
    """获取 UTC 时间，格式 YYYYMMDDHH（华为云要求）"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y%m%d%H")

def generate_password(timestamp: str, secret: str) -> str:
    """
    华为云规则: Password = Hex(HMAC-SHA256(key=timestamp, data=secret))
    注意：key 和 data 的顺序容易搞反！
    """
    return hmac.new(
        timestamp.encode("utf-8"),
        secret.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

# ============================================================
#              模拟传感器数据生成
# ============================================================
class SensorSimulator:
    """模拟传感器数据，带一定的连续性和随机波动"""
    def __init__(self, on_pump_change=None):
        self.temperature = 22.0
        self.humidity = 55.0
        self.soil_moisture = 40.0
        self.pump_status = False
        self._on_pump_change = on_pump_change  # 泵状态变化回调

    def generate(self):
        """
        生成模拟的传感器数据（华为云 IoTDA 格式）
        注意：必须使用 services 数组包装，否则华为云无法识别！
        """
        # 温度：缓慢变化，偶尔波动
        self.temperature += random.uniform(-0.5, 0.5)
        self.temperature = max(15.0, min(35.0, self.temperature))

        # 湿度：与温度负相关，加入随机性
        self.humidity += random.uniform(-2.0, 2.0)
        self.humidity = max(20.0, min(90.0, self.humidity))

        # 土壤湿度：如果水泵开启，逐渐上升
        if self.pump_status:
            self.soil_moisture += random.uniform(0.5, 1.5)
        else:
            self.soil_moisture -= random.uniform(0.1, 0.3)
        self.soil_moisture = max(10.0, min(95.0, self.soil_moisture))

        # ✅ 华为云 IoTDA 要求的数据格式
        return {
            "services": [
                {
                    "service_id": "sensor_data",
                    "properties": {
                        "temperature":      round(self.temperature, 1),
                        "humidity":         round(self.humidity, 1),
                        "soil_moisture":   round(self.soil_moisture, 1),
                        "pump_status":      self.pump_status,
                        "wifi_signal":     random.randint(-75, -55),
                        "firmware_version": "1.0.0"
                    },
                    "event_time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                }
            ]
        }

    def set_pump(self, status: bool, duration: float = 0):
        """
        设置水泵状态
        duration: 开泵时长（秒），>0 时自动在 duration 秒后关泵
        """
        old_status = self.pump_status
        self.pump_status = status
        # 取消之前的定时器（如果存在）
        if hasattr(self, '_pump_timer') and self._pump_timer:
            self._pump_timer.cancel()
            self._pump_timer = None
        # 如果指定了时长，启动定时器自动关泵
        if status and duration > 0:
            self._pump_timer = threading.Timer(duration, self._auto_stop_pump)
            self._pump_timer.daemon = True
            self._pump_timer.start()
        # 状态变化时触发回调
        if old_status != status and self._on_pump_change:
            self._on_pump_change(status, duration if status else 0)

    def _auto_stop_pump(self):
        """定时器回调：自动关泵"""
        self.pump_status = False
        print(f"\n[水泵] [AUTO] 定时器触发，水泵自动关闭")
        if self._on_pump_change:
            self._on_pump_change(False, 0)

# ============================================================
#               MQTT 回调函数（paho-mqtt v2 原生 API）
# ============================================================
def on_connect(client, userdata, flags, reason_code, properties=None):
    """v2 回调: reason_code 是 ReasonCode 对象，0 表示成功"""
    rc = reason_code.value if hasattr(reason_code, 'value') else reason_code
    if rc == 0:
        print(f"[MQTT] [OK] 连接成功! device_id={DEVICE_ID}")
        client.subscribe(SUBSCRIBE_TOPIC, qos=1)
        print(f"[MQTT] [OK] 已订阅命令 Topic: {SUBSCRIBE_TOPIC}")
    else:
        print(f"[MQTT] [FAIL] 连接失败, rc={rc}, reason={reason_code}")
        sys.exit(1)

def on_subscribe(client, userdata, mid, reason_code_list, properties=None):
    print(f"[MQTT] [OK] 订阅确认, mid={mid}")

def on_message(client, userdata, msg):
    """收到云端下发的命令"""
    print(f"\n{'='*60}")
    print(f"[命令] [RECV] 收到云端指令!")
    print(f"[命令] Topic: {msg.topic}")
    print(f"[命令] Payload (raw): {msg.payload}")
    
    # 从 Topic 中提取 request_id
    # Topic 格式: $oc/devices/{id}/sys/commands/request_id={request_id}
    request_id = ""
    if "request_id=" in msg.topic:
        request_id = msg.topic.split("request_id=")[-1]
    
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        print(f"[命令] Payload (JSON):")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        # 解析常见命令格式
        parse_and_execute_command(client, payload, request_id)
    except json.JSONDecodeError:
        print(f"[命令] [WARN] 无法解析 JSON，原始内容: {msg.payload}")
    except Exception as e:
        print(f"[命令] [FAIL] 解析异常: {e}")
    print(f"{'='*60}\n")

def parse_and_execute_command(client, payload: dict, request_id: str = ""):
    """
    解析云端下发的控制命令，模拟执行，并上报执行结果
    
    华为云下发命令格式（platform -> device）：
    {
        "paras": {"time": 3},           // 命令参数
        "service_id": "openWater",      // 服务ID
        "command_name": "openWater"     // 命令名
    }
    
    支持的 service_id/command_name 组合：
    - openWater: 水泵控制，paras.time = 开泵秒数（0 = 关泵）
    - 也兼容自定义格式：paras 里有 "pump" 字段
    """
    print(f"[执行] [PARSE] 解析命令...")
    
    service_id   = payload.get("service_id", "")
    command_name = payload.get("command_name", "")
    paras        = payload.get("paras", {})
    
    print(f"[执行] [INFO] service_id={service_id}, command_name={command_name}")
    print(f"[执行] [INFO] paras={json.dumps(paras, ensure_ascii=False)}")
    
    # ======== openWater 服务：水泵控制 ========
    if service_id == "openWater":
        pump_time = paras.get("time", 0)
        
        if pump_time > 0:
            sensor_simulator.set_pump(True, duration=pump_time)
            execution_result = "success"
            message = f"水泵已开启，持续 {pump_time} 秒"
            print(f"[执行] [PUMP] 开泵, 时长={pump_time}s（{pump_time}秒后自动关泵）")
        else:
            sensor_simulator.set_pump(False)
            execution_result = "success"
            message = "水泵已关闭"
            print(f"[执行] [PUMP] 关泵")
        
        print(f"[执行] [OK] 模拟: {message}")
    
    else:
        print(f"[执行] [WARN] 未知命令格式，完整内容:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    
    # ======== 上报执行结果 ========
    
    # 1) 华为云命令响应（平台要求格式，必须带 request_id）
    # Topic: $oc/devices/{device_id}/sys/commands/response/request_id={request_id}
    # 数据格式: {"result_code": 0, "response_name": "COMMAND_RESPONSE", "paras": {"result": "success"}}
    response_topic = f"$oc/devices/{DEVICE_ID}/sys/commands/response/request_id={request_id}"
    platform_response = {
        "result_code": 0,
        "response_name": "COMMAND_RESPONSE",
        "paras": {
            "result": execution_result
        }
    }
    client.publish(response_topic, json.dumps(platform_response), qos=1)
    print(f"[执行] [RESP] 已回复平台: {response_topic}")
    print(f"[执行] [RESP] Payload: {json.dumps(platform_response, ensure_ascii=False)}")
    
# ============================================================
#              上报方法
# ============================================================

def report_sensor_data(client, report_count_ref):
    """上报传感器数据到 messages/up → 规则引擎 → HTTP 转发 → 自建服务器"""
    report_count_ref[0] += 1
    data = sensor_simulator.generate()
    payload = json.dumps(data)

    print(f"[上报] [SEND] 第 {report_count_ref[0]} 次上报:")
    print(f"[上报]   Payload: {payload}")
    print(f"[上报]   消息 → {MESSAGE_TOPIC}")
    info = client.publish(MESSAGE_TOPIC, payload, qos=1)
    info.wait_for_publish(timeout=5)

def on_publish(client, userdata, mid, reason_code, properties=None):
    pass

def on_disconnect(client, userdata, flags, reason_code, properties=None):
    rc = reason_code.value if hasattr(reason_code, 'value') else reason_code
    print(f"[MQTT] [WARN] 连接断开, rc={rc}")
    if rc != 0:
        print(f"[MQTT] [RETRY] 尝试自动重连...")

# ============================================================
#                   主程序
# ============================================================

# 全局传感器模拟器（回调在 main 中注册）
sensor_simulator = SensorSimulator()

def main():
    parser = argparse.ArgumentParser(description="ESP8266 设备模拟器（完整版）")
    parser.add_argument("--mode", choices=["dynamic", "pregen"], default="dynamic",
                        help="密码模式: dynamic=动态密码, pregen=预生成密码")
    parser.add_argument("--password", type=str, default="",
                        help="预生成密码（mode=pregen 时必填）")
    parser.add_argument("--port", type=int, default=MQTT_PORT,
                        help=f"MQTT 端口 (默认 {MQTT_PORT})")
    parser.add_argument("--interval", type=int, default=REPORT_INTERVAL,
                        help=f"上报间隔秒数 (默认 {REPORT_INTERVAL}s)")
    parser.add_argument("--log", action="store_true",
                        help="启用日志记录到文件")
    args = parser.parse_args()

    # -------- 配置日志 --------
    if args.log:
        log_file = f"device_simulator_{DEVICE_ID}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        print(f"[配置] 日志已启用: {log_file}")

    # -------- 构造 ClientID（与 ESP8266 一致）--------
    if args.mode == "dynamic":
        timestamp = get_utc_timestamp_hour()
        password  = generate_password(timestamp, DEVICE_SECRET)
        client_id = f"{DEVICE_ID}_0_0_{timestamp}"
        username  = DEVICE_ID
        print(f"[配置] 模式: 动态密码")
        print(f"[配置] Timestamp: {timestamp}")
        print(f"[配置] Password : {password[:16]}... (len={len(password)})")
    else:
        if not args.password:
            print("[FAIL] 预生成密码模式需要 --password 参数")
            sys.exit(1)
        password  = args.password
        client_id = f"{DEVICE_ID}_0_0_0"   # 预生成密码 clientId 末尾是 0
        username  = DEVICE_ID
        print(f"[配置] 模式: 预生成密码")

    print(f"[配置] ClientID : {client_id} ({len(client_id)} 字符)")
    print(f"[配置] Username : {username}")
    print(f"[配置] Host     : {MQTT_HOST}:{args.port}")
    print()

    # -------- 创建 MQTT 客户端（paho-mqtt v2 原生 API）--------
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311
    )

    client.username_pw_set(username, password)

    # 非 TLS 端口
    if args.port == 1883:
        print("[MQTT] 使用非加密连接 (port 1883)")
    else:
        print("[MQTT] 使用 TLS 加密连接 (port 8883)")
        context = ssl.create_default_context()
        client.tls_set_context(context)
        client.tls_insecure_set(True)  # 跳过证书验证（测试用）

    # 注册回调
    client.on_connect    = on_connect
    client.on_subscribe  = on_subscribe
    client.on_message    = on_message
    client.on_publish    = on_publish
    client.on_disconnect = on_disconnect

    # -------- 连接 --------
    try:
        print(f"[MQTT] 正在连接 {MQTT_HOST}:{args.port} ...")
        client.connect(MQTT_HOST, args.port, keepalive=60)
    except Exception as e:
        print(f"[MQTT] [FAIL] 连接异常: {e}")
        sys.exit(1)

    client.loop_start()

    # 等待连接建立
    time.sleep(2)

    # -------- 注册泵状态变化回调：变化时立即上报 --------
    report_count_ref = [0]

    def on_pump_changed(status, duration):
        print(f"\n[水泵] [EVENT] 泵状态变化 → {'开' if status else '关'}, 时长={duration}s, 立即上报传感器数据...")
        report_sensor_data(client, report_count_ref)

    sensor_simulator._on_pump_change = on_pump_changed

    # -------- 主循环：定时上报数据 --------
    print(f"\n[主循环] 开始模拟上报，间隔 = {args.interval}s，按 Ctrl+C 退出\n")
    print(f"[主循环] 上报 Topic: {MESSAGE_TOPIC}")
    print()
    last_password_update = time.time()

    try:
        while True:
            report_sensor_data(client, report_count_ref)

            # 检查是否需要更新动态密码（仅动态模式）
            if args.mode == "dynamic":
                if time.time() - last_password_update > PASSWORD_UPDATE_INTERVAL:
                    print(f"\n[维护] [PASSWORD] 动态密码即将过期，正在更新...")
                    new_timestamp = get_utc_timestamp_hour()
                    new_password  = generate_password(new_timestamp, DEVICE_SECRET)
                    new_client_id = f"{DEVICE_ID}_0_0_{new_timestamp}"

                    client.username_pw_set(DEVICE_ID, new_password)
                    print(f"[维护] [PASSWORD] 密码已更新 (timestamp={new_timestamp})")
                    last_password_update = time.time()

            # 等待下次上报
            for i in range(args.interval):
                time.sleep(1)
                if not client.is_connected():
                    print("[主循环] [WARN] MQTT 连接已断开，等待重连...")
                    time.sleep(2)

    except KeyboardInterrupt:
        print("\n[主循环] [EXIT] 用户中断，正在退出...")
    except Exception as e:
        print(f"\n[主循环] [FAIL] 异常: {e}")
    finally:
        print("[主循环] [CLOSE] 断开 MQTT 连接...")
        client.loop_stop()
        client.disconnect()
        print("[主循环] [OK] 已退出")

if __name__ == "__main__":
    main()
