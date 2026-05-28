"""
华为云 IoTDA MQTT 连接测试脚本
用 paho-mqtt 在电脑上验证连接参数是否正确
"""

import ssl
import json
import time
from paho.mqtt import client as mqtt_client

# ==================== 华为云连接参数 ====================
HOST = "923924d24d.st1.iotda-device.cn-east-3.myhuaweicloud.com"
PORT = 8883
CLIENT_ID = "6a17a638e094d61592419546_00001_0_0_2026052814"
USERNAME = "6a17a638e094d61592419546_00001"
PASSWORD = "c45d75f6216842a052a5c8f38408195d0a5f0e6fcab40c291390f45b7ec5dfeb"

# ==================== Topic 定义 ====================
DEVICE_ID = "6a17a638e094d61592419546_00001"
TOPIC_REPORT = f"$oc/devices/{DEVICE_ID}/sys/properties/report"
TOPIC_DOWN = f"$oc/devices/{DEVICE_ID}/sys/messages/down"
TOPIC_UP = f"$oc/devices/{DEVICE_ID}/sys/messages/up"


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"\n[连接结果] reason_code = {reason_code}")
    if reason_code == 0:
        print("[连接成功!] 已连接到华为云 IoTDA")
        # 订阅下行命令 Topic
        result = client.subscribe(TOPIC_DOWN, qos=1)
        print(f"[订阅] Topic: {TOPIC_DOWN}, 结果: {result}")
    else:
        print(f"[连接失败!] 错误码: {reason_code}")
        print("  0 = 成功")
        print("  1 = 协议版本不支持")
        print("  2 = ClientID 被拒绝")
        print("  3 = 服务不可用")
        print("  4 = 用户名密码错误")
        print("  5 = 未授权")


def on_disconnect(client, userdata, reason_code, properties=None):
    print(f"\n[断开连接] reason_code = {reason_code}")


def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print(f"[订阅成功] mid={mid}, qos={granted_qos}")


def on_message(client, userdata, msg):
    print(f"\n[收到消息] Topic: {msg.topic}")
    print(f"  Payload: {msg.payload.decode('utf-8')}")


def on_publish(client, userdata, mid, reason_code, properties=None):
    print(f"[发布成功] mid={mid}")


def test_mqtt():
    print("=" * 50)
    print("  华为云 IoTDA MQTT 连接测试")
    print("=" * 50)
    print(f"  Host:     {HOST}:{PORT}")
    print(f"  ClientID: {CLIENT_ID}")
    print(f"  Username: {USERNAME}")
    print(f"  Password: {PASSWORD[:16]}...")
    print("=" * 50)

    # 创建客户端（MQTT v3.1.1，华为云要求）
    client = mqtt_client.Client(
        client_id=CLIENT_ID,
        protocol=mqtt_client.MQTTv311,
        clean_session=True
    )

    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_publish = on_publish

    # TLS 配置（跳过证书验证，测试用）
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    print("\n[连接中...]")
    try:
        client.connect(HOST, PORT, keepalive=120)
    except Exception as e:
        print(f"[连接异常] {type(e).__name__}: {e}")
        return

    # 启动网络循环（非阻塞）
    client.loop_start()

    # 等待连接结果
    time.sleep(3)

    if not client.is_connected():
        print("\n[测试失败] 未能在3秒内建立连接")
        client.loop_stop()
        return

    # 等一下确保订阅完成
    time.sleep(2)

    # 发送模拟传感器数据
    print("\n[发送模拟数据...]")
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
    print(f"  Topic: {TOPIC_REPORT}")
    print(f"  Data:  {payload}")
    client.publish(TOPIC_REPORT, payload, qos=1)

    # 保持连接等待消息
    print("\n[保持连接中，等待30秒观察...]")
    print("  (华为云可能会下发设备命令)")
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
    test_mqtt()
