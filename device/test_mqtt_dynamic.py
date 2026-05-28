"""
华为云 IoTDA MQTT 连接测试 - 动态密码模式（设备密钥）
用 DEVICE_SECRET 动态生成 clientId 和 password
"""

import ssl
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from paho.mqtt import client as mqtt_client

# ==================== 华为云连接参数 ====================
HOST = "923924d24d.st1.iotda-device.cn-east-3.myhuaweicloud.com"
PORT = 8883
DEVICE_ID = "6a17a638e094d61592419546_00001"
DEVICE_SECRET = "Cyy542100312"  # 设备密钥

# ==================== 动态密码生成 ====================
def get_timestamp() -> str:
    """
    获取当前 UTC 时间戳，格式: YYYYMMDDHH（精确到小时）
    """
    utc_now = datetime.now(timezone.utc)
    return utc_now.strftime("%Y%m%d%H")


def generate_password(timestamp: str) -> str:
    """
    华为云 IoTDA MQTT 密码生成规则:
    Password = Hex(HMAC-SHA256(key=时间戳, data=设备密钥))
    注意: key 是时间戳, data 是设备密钥, 输出是 Hex 编码!
    """
    key = timestamp.encode("utf-8")
    msg = DEVICE_SECRET.encode("utf-8")
    signature = hmac.new(key, msg, hashlib.sha256).digest()
    return signature.hex()  # Hex 编码, 不是 Base64!


def build_client_id(timestamp: str) -> str:
    """ClientId 格式: {DeviceID}_0_0_{timestamp}"""
    return f"{DEVICE_ID}_0_0_{timestamp}"


# ==================== Topic 定义 ====================
TOPIC_REPORT = f"$oc/devices/{DEVICE_ID}/sys/properties/report"
TOPIC_DOWN = f"$oc/devices/{DEVICE_ID}/sys/messages/down"
TOPIC_UP = f"$oc/devices/{DEVICE_ID}/sys/messages/up"


# ==================== MQTT 回调 ====================
def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"\n[连接结果] reason_code = {reason_code}")
    codes = {0: "成功", 1: "协议版本不支持", 2: "ClientID被拒绝",
             3: "服务不可用", 4: "用户名密码错误", 5: "未授权"}
    print(f"  含义: {codes.get(reason_code, '未知')}")

    if reason_code == 0:
        result = client.subscribe(TOPIC_DOWN, qos=1)
        print(f"[订阅] Topic: {TOPIC_DOWN}")


def on_disconnect(client, userdata, reason_code, properties=None):
    print(f"\n[断开连接] reason_code = {reason_code}")


def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print(f"[订阅成功] qos={granted_qos}")


def on_message(client, userdata, msg):
    print(f"\n[收到消息] Topic: {msg.topic}")
    print(f"  Payload: {msg.payload.decode('utf-8')}")


def test_dynamic_password():
    print("=" * 55)
    print("  华为云 IoTDA MQTT 连接测试 - 动态密码模式")
    print("=" * 55)
    print(f"  Host:         {HOST}:{PORT}")
    print(f"  DeviceID:     {DEVICE_ID}")
    print(f"  DeviceSecret: {DEVICE_SECRET}")
    print("=" * 55)

    # 生成时间戳和密码
    timestamp = get_timestamp()
    password = generate_password(timestamp)
    client_id = build_client_id(timestamp)

    print(f"\n[动态生成]")
    print(f"  时间戳:  {timestamp}")
    print(f"  ClientID: {client_id}")
    print(f"  Username: {DEVICE_ID}")
    print(f"  Password: {password}")
    print(f"  HMAC输入: {timestamp}")
    print(f"  HMAC密钥: {DEVICE_SECRET}")

    # 创建客户端
    client = mqtt_client.Client(
        client_id=client_id,
        protocol=mqtt_client.MQTTv311,
        clean_session=True
    )
    client.username_pw_set(DEVICE_ID, password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_subscribe = on_subscribe
    client.on_message = on_message

    # TLS 配置
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    print("\n[连接中...]")
    try:
        client.connect(HOST, PORT, keepalive=120)
    except Exception as e:
        print(f"[连接异常] {type(e).__name__}: {e}")
        return

    client.loop_start()
    time.sleep(3)

    if not client.is_connected():
        print("\n[测试失败] 未能建立连接")
        # 验证一下 HMAC 手动计算
        print("\n--- 手动验证 HMAC-SHA256 ---")
        ts = get_timestamp()
        sig = hmac.new(
            DEVICE_SECRET.encode(), ts.encode(), hashlib.sha256
        ).digest()
        pwd = base64.b64encode(sig).decode()
        print(f"  timestamp: {ts}")
        print(f"  password:  {pwd}")
        print(f"  password length: {len(pwd)}")
        client.loop_stop()
        return

    # 等订阅完成
    time.sleep(2)

    # 发送模拟数据
    print("\n[发送模拟传感器数据...]")
    payload = json.dumps({
        "services": [{
            "service_id": "sensor",
            "properties": {
                "temperature": 26.6,
                "humidity": 75,
                "soil_moisture": 43,
                "pump_status": False,
                "wifi_signal": -60,
                "firmware_version": "1.0.0"
            }
        }]
    })
    client.publish(TOPIC_REPORT, payload, qos=1)

    print("\n[保持连接 30 秒，观察是否有下行命令...]")
    print("  (华为云控制台 -> 设备 -> 命令下发 可以测试)")
    print("  (Ctrl+C 提前退出)")
    try:
        for i in range(30):
            time.sleep(1)
            if i % 10 == 0:
                print(f"  ... {i}秒")
    except KeyboardInterrupt:
        print("\n[用户中断]")

    client.loop_stop()
    client.disconnect()
    print("\n[测试结束]")


if __name__ == "__main__":
    test_dynamic_password()
