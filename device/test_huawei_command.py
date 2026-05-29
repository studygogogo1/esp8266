#!/usr/bin/env python3
"""
华为云IoTDA 测试脚本（命令下发 + 数据监听）
- 命令下发：通过 SDK CreateCommand API（需要 AK/SK）
- 数据监听：通过 MQTT 订阅 devicelog（规则引擎转发）

用法：
    python test_huawei_command.py              # 开水泵 30 秒
    python test_huawei_command.py off          # 关水泵
    python test_huawei_command.py on 60        # 开水泵 60 秒
    python test_huawei_command.py listen       # 仅监听设备数据上报（持续运行）
"""

import hashlib
import hmac
import json
import sys
import time
import datetime
import paho.mqtt.client as mqtt

# 华为云 SDK（命令下发用）
from huaweicloudsdkcore.auth.credentials import BasicCredentials, DerivedCredentials
from huaweicloudsdkcore.region.region import Region as CoreRegion
from huaweicloudsdkiotda.v5 import *
from huaweicloudsdkiotda.v5.region.iotda_region import IoTDARegion

# ============================================================
#                      配置区
# ============================================================

# server1 设备（负责下发命令/监听数据的一端）
SERVER_DEVICE_ID     = "6a17a638e094d61592419546_server1"
SERVER_DEVICE_SECRET = "Cyy542100312"

# 目标设备（接收命令/上报数据的一端）
TARGET_DEVICE_ID     = "6a17a638e094d61592419546_00001"

# MQTT 服务器
MQTT_HOST = "923924d24d.st1.iotda-device.cn-east-3.myhuaweicloud.com"
MQTT_PORT = 1883

# 命令下发 Topic
REQUEST_ID      = str(int(time.time() * 1000))
COMMAND_TOPIC   = f"$oc/devices/{TARGET_DEVICE_ID}/sys/commands/request_id={REQUEST_ID}"

# 订阅目标设备的命令响应 Topic
RESPONSE_TOPIC  = f"$oc/devices/{TARGET_DEVICE_ID}/sys/commands/response/request_id={REQUEST_ID}"

# 数据接收 Topic（规则引擎：设备消息 → MQTT推送消息队列 → devicelog）
DATA_REPORT_TOPIC = "devicelog"

# 等待响应超时（秒）
RESPONSE_TIMEOUT = 15

# SDK API 配置（命令下发用，需与服务端 settings 一致）
HUAWEI_AK = "HPUAN1B4JPAKJJLLPWM1"
HUAWEI_SK = "hKbkdYNW61Lhtlu7Iphz7XIKaQUG1PRIrCb15kuX"
HUAWEI_PROJECT_ID = "16512cefc56d4bbc9cff96234619b8aa"
HUAWEI_REGION = "cn-east-3"
HUAWEI_ENDPOINT = "923924d24d.st1.iotda-app.cn-east-3.myhuaweicloud.com"
HUAWEI_INSTANCE_ID = "e01941fb-c614-415f-98cb-5d776280d89a"


# ============================================================
#              动态密码生成（华为云 HMAC-SHA256 规则）
# ============================================================
def get_timestamp():
    """UTC 时间，格式 YYYYMMDDHH"""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H")


def generate_password(timestamp: str, secret: str) -> str:
    """
    华为云规则: Password = Hex(HMAC-SHA256(key=timestamp, data=secret))
    """
    return hmac.new(
        timestamp.encode("utf-8"),
        secret.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def make_client_id(device_id: str, timestamp: str) -> str:
    """
    ClientID 格式: {device_id}_0_0_{timestamp}
    """
    return f"{device_id}_0_0_{timestamp}"


# ============================================================
#                   SDK 命令下发
# ============================================================
def send_command_via_sdk(device_id: str, command: dict) -> bool:
    """通过华为云 SDK API 下发命令（paras 必须是 JSON 对象）"""
    credentials = BasicCredentials(HUAWEI_AK, HUAWEI_SK, HUAWEI_PROJECT_ID) \
        .with_derived_predicate(DerivedCredentials.get_default_derived_predicate())

    client = IoTDAClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(CoreRegion(id=HUAWEI_REGION, endpoint=HUAWEI_ENDPOINT)) \
        .build()

    try:
        # 将命令行参数转换为产品模型格式
        # service_id="openWater", command_name="openWater", paras={"time": N}
        pump_action = command.get("pump", "off")
        duration    = command.get("duration", 0)
        pump_time   = duration if pump_action == "on" else 0
        
        request = CreateCommandRequest()
        request.device_id = device_id
        request.instance_id = HUAWEI_INSTANCE_ID
        request.body = DeviceCommandRequest(
            service_id="openWater",
            command_name="openWater",
            paras={"time": pump_time},
        )
        response = client.create_command(request)
        print(f"[SDK] 命令下发成功! command_id={response.command_id}, time={pump_time}s")
        return True
    except Exception as e:
        print(f"[SDK] 命令下发失败: {e}")
        return False


# ============================================================
#                   MQTT 回调
# ============================================================
response_received = False
response_payload  = None
data_count        = 0


def on_connect(client, userdata, flags, reason_code, properties=None):
    rc = reason_code.value if hasattr(reason_code, "value") else reason_code
    if rc == 0:
        print(f"[MQTT] 连接成功 (server1 身份)")

        # 订阅目标设备的命令响应 Topic
        client.subscribe(RESPONSE_TOPIC, qos=1)
        print(f"[MQTT] 已订阅命令响应 Topic: {RESPONSE_TOPIC}")

        # 订阅目标设备的数据上报 Topic
        client.subscribe(DATA_REPORT_TOPIC, qos=1)
        print(f"[MQTT] 已订阅数据上报 Topic: {DATA_REPORT_TOPIC}")
    else:
        print(f"[MQTT] 连接失败, rc={rc}")
        sys.exit(1)


def on_message(client, userdata, msg):
    global response_received, response_payload, data_count

    topic = msg.topic

    # ---------- 判断消息类型 ----------
    if "messages/up" in topic or "properties/report" in topic or topic == DATA_REPORT_TOPIC:
        # 设备数据上报（消息上报/属性上报/规则引擎转发）
        data_count += 1
        _handle_device_data(topic, msg.payload)
    elif "commands/response" in topic:
        # 命令响应回执
        print(f"\n[响应] 收到设备命令回执!")
        _handle_command_response(topic, msg.payload)
        response_received = True
    else:
        # 其他未知 topic
        print(f"\n[消息] 收到未知 Topic 的消息:")
        print(f"  Topic: {topic}")
        print(f"  Payload: {msg.payload}")


def _handle_device_data(topic: str, raw_payload: bytes):
    """处理设备上报的传感器数据"""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    try:
        payload = json.loads(raw_payload.decode("utf-8"))

        # 从 services[0].properties 中提取数据
        properties = payload
        if "services" in payload and isinstance(payload["services"], list):
            for svc in payload["services"]:
                if "properties" in svc:
                    properties = svc["properties"]
                    break

        # 格式化输出
        temp = properties.get("temperature", "--")
        humi = properties.get("humidity", "--")
        soil = properties.get("soil_moisture", "--")
        pump = properties.get("pump_status", "--")
        wifi = properties.get("wifi_signal", "--")
        fw   = properties.get("firmware_version", "--")

        print(f"[{now}] #{data_count:03d} | 温度:{temp}°C  湿度:{humi}%  土壤:{soil}%  水泵:{pump}  WiFi:{wifi}dBm  固件:{fw}")

    except Exception as e:
        print(f"[{now}] #{data_count:03d} | 数据解析失败: {e}")
        print(f"         原始: {raw_payload}")


def _handle_command_response(topic: str, raw_payload: bytes):
    """处理命令响应回执"""
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
        print(f"  Topic: {topic}")
        print(f"  内容: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    except Exception:
        print(f"  Topic: {topic}")
        print(f"  原始内容: {raw_payload}")


def on_publish(client, userdata, mid, reason_code=None, properties=None):
    print(f"[发送] 命令已投递到 MQTT Broker, mid={mid}")


def on_subscribe(client, userdata, mid, reason_code_list, properties=None):
    print(f"[订阅] 确认, mid={mid}")


def on_disconnect(client, userdata, flags, reason_code, properties=None):
    rc = reason_code.value if hasattr(reason_code, "value") else reason_code
    print(f"\n[MQTT] 连接断开, rc={rc}")


# ============================================================
#                     主流程
# ============================================================
def main():
    global action, duration

    # 解析参数
    mode     = "command"  # "command" 或 "listen"
    action   = "on"
    duration = 30

    if len(sys.argv) > 1:
        arg1 = sys.argv[1].lower()
        if arg1 == "listen":
            mode = "listen"
        elif arg1 in ("on", "off"):
            action = arg1
        else:
            print(f"用法: python test_huawei_command.py [on|off|listen] [duration_seconds]")
            sys.exit(1)

    if mode == "command" and len(sys.argv) > 2:
        try:
            duration = int(sys.argv[2])
        except ValueError:
            print(f"时长必须是数字: {sys.argv[2]}")
            sys.exit(1)

    if action == "off":
        duration = 0

    # 打印信息
    print()
    print("=" * 60)
    if mode == "listen":
        print("  华为云IoTDA MQTT 数据监听模式")
        print("=" * 60)
        print(f"  监听方: {SERVER_DEVICE_ID}")
        print(f"  目标设备: {TARGET_DEVICE_ID}")
        print(f"  监听 Topic: {DATA_REPORT_TOPIC}")
        print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  模式: 持续监听，按 Ctrl+C 退出")
    else:
        print("  华为云IoTDA MQTT 命令下发测试")
        print("=" * 60)
        print(f"  发送方: {SERVER_DEVICE_ID}")
        print(f"  目标设备: {TARGET_DEVICE_ID}")
        print(f"  命令: pump={action}, duration={duration}s")
        print(f"  同时监听: {DATA_REPORT_TOPIC}")
        print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 生成认证信息
    timestamp = get_timestamp()
    password  = generate_password(timestamp, SERVER_DEVICE_SECRET)
    client_id = make_client_id(SERVER_DEVICE_ID, timestamp)

    print(f"[认证] Timestamp: {timestamp}")
    print(f"[认证] ClientID : {client_id}")
    print(f"[认证] Password : {password[:16]}...")
    print()

    # 创建 MQTT 客户端（paho-mqtt v2）
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv311
    )
    client.username_pw_set(SERVER_DEVICE_ID, password)

    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_publish    = on_publish
    client.on_subscribe  = on_subscribe
    client.on_disconnect = on_disconnect

    # 连接
    print(f"[连接] {MQTT_HOST}:{MQTT_PORT} ...")
    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"[连接] 失败: {e}")
        sys.exit(1)

    client.loop_start()

    # 等待连接建立
    time.sleep(2)

    # -------- 命令模式 --------
    if mode == "command":
        # 构造命令 payload
        command_payload = {
            "pump": action,
            "duration": duration
        }

        # 通过 SDK API 下发命令（而不是 MQTT publish）
        print()
        print(f"[发送] 通过 SDK API 下发命令...")
        print(f"[发送] 目标设备: {TARGET_DEVICE_ID}")
        print(f"[发送] 命令: {json.dumps(command_payload, ensure_ascii=False)}")
        send_command_via_sdk(TARGET_DEVICE_ID, command_payload)

        # 等待设备响应
        print()
        print(f"[等待] 等待命令响应（最多 {RESPONSE_TIMEOUT} 秒）...")
        print(f"[等待] 同时持续监听设备数据上报...")
        deadline = time.time() + RESPONSE_TIMEOUT
        while not response_received and time.time() < deadline:
            time.sleep(0.5)

        # 结果
        print()
        print("=" * 60)
        if response_received:
            print("✅ 成功！设备已收到命令并返回响应。")
        else:
            print("⚠️  命令已发送，但未收到命令响应。")
            print("   可能原因：")
            print("   1. 目标设备未在线（先运行 device_simulator.py）")
            print("   2. 设备不支持该 Topic 格式")
        print(f"   期间收到 {data_count} 条设备数据上报")
        print("=" * 60)

    # -------- 监听模式 --------
    else:
        print()
        print("开始监听设备数据上报，按 Ctrl+C 退出...")
        print("-" * 60)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n\n[结束] 共收到 {data_count} 条设备数据上报")

    client.loop_stop()
    client.disconnect()
    print("[退出] 已断开 MQTT 连接")
    print()


if __name__ == "__main__":
    main()
