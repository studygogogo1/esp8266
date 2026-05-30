#!/usr/bin/env python3
"""
测试指令下发功能
- 调用后端API，触发水泵控制指令
- 用于测试华为云IoTDA消息下发是否成功
"""

import requests
import json
import time

# 后端API地址
BASE_URL = "http://121.40.187.191:8000"

# 测试设备ID（从之前的API返回中获得）
DEVICE_ID = "6a17a638e094d61592419546_00001"


def test_pump_on():
    """测试开启水泵"""
    print("=" * 80)
    print("测试1: 开启水泵")
    print("=" * 80)

    url = f"{BASE_URL}/api/devices/{DEVICE_ID}/pump"
    payload = {
        "action": "on",
        "duration": 30
    }

    print(f"请求 URL: {url}")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False)}")
    print()

    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应体: {response.text}")
        print()

        if response.status_code == 200:
            print("✅ 指令下发成功！")
            print("   请检查你的测试客户端是否收到消息:")
            print(f"   Topic: $oc/devices/{DEVICE_ID}/user/pump")
            print(f"   消息: {json.dumps(payload)}")
            return True
        else:
            print("❌ 指令下发失败！")
            return False

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_pump_off():
    """测试关闭水泵"""
    print("=" * 80)
    print("测试2: 关闭水泵")
    print("=" * 80)

    url = f"{BASE_URL}/api/devices/{DEVICE_ID}/pump"
    payload = {
        "action": "off",
        "duration": 0
    }

    print(f"请求 URL: {url}")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False)}")
    print()

    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应体: {response.text}")
        print()

        if response.status_code == 200:
            print("✅ 指令下发成功！")
            print("   请检查你的测试客户端是否收到消息:")
            print(f"   Topic: $oc/devices/{DEVICE_ID}/user/pump")
            print(f"   消息: {json.dumps(payload)}")
            return True
        else:
            print("❌ 指令下发失败！")
            return False

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_get_device():
    """测试获取设备信息"""
    print("=" * 80)
    print("测试3: 获取设备信息")
    print("=" * 80)

    url = f"{BASE_URL}/api/devices/{DEVICE_ID}"

    print(f"请求 URL: {url}")
    print()

    try:
        response = requests.get(url, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应体: {response.text}")
        print()

        if response.status_code == 200:
            print("✅ 获取设备信息成功！")
            return True
        else:
            print("❌ 获取设备信息失败！")
            return False

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_list_devices():
    """测试获取设备列表"""
    print("=" * 80)
    print("测试4: 获取设备列表")
    print("=" * 80)

    url = f"{BASE_URL}/api/devices/"

    print(f"请求 URL: {url}")
    print()

    try:
        response = requests.get(url, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应体: {response.text[:500]}...")  # 只显示前500字符
        print()

        if response.status_code == 200:
            print("✅ 获取设备列表成功！")
            return True
        else:
            print("❌ 获取设备列表失败！")
            return False

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def main():
    """主函数"""
    print()
    print("🚀 开始测试指令下发功能")
    print(f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 检查后端是否在线
    print("检查后端服务是否在线...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ 后端服务在线")
        else:
            print("❌ 后端服务异常")
            return
    except Exception as e:
        print(f"❌ 无法连接到后端: {e}")
        print("   请检查:")
        print("   1. 后端服务是否启动")
        print("   2. 防火墙是否开放8000端口")
        print("   3. IP地址是否正确")
        return

    print()
    print("-" * 80)
    print()

    # 执行测试
    results = []

    # 测试1: 获取设备列表
    results.append(("获取设备列表", test_list_devices()))
    time.sleep(1)

    # 测试2: 获取设备信息
    results.append(("获取设备信息", test_get_device()))
    time.sleep(1)

    # 测试3: 开启水泵
    results.append(("开启水泵", test_pump_on()))
    print()
    print("⏳ 等待5秒，检查你的测试客户端是否收到消息...")
    time.sleep(5)

    # 测试4: 关闭水泵
    results.append(("关闭水泵", test_pump_off()))
    print()
    print("⏳ 等待5秒，检查你的测试客户端是否收到消息...")
    time.sleep(5)

    # 汇总结果
    print()
    print("=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    for name, result in results:
        status = "✅ 成功" if result else "❌ 失败"
        print(f"{name}: {status}")

    print()
    print("📋 下一步操作:")
    print("   1. 检查你的测试客户端（device_simulator.py）是否收到消息")
    print("   2. 查看后端日志: tail -f /path/to/esp8266-main/server/logs/app.log")
    print("   3. 查看华为云IoTDA控制台，确认命令是否下发成功")
    print()


if __name__ == "__main__":
    main()
