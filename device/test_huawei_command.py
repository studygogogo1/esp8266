#!/usr/bin/env python3
"""
华为云 IoTDA 命令下发测试脚本（纯 SDK API，不需要 MQTT）
- 通过 SDK CreateCommand API 下发控制命令到设备

用法：
    python test_huawei_command.py              # 开水泵 30 秒
    python test_huawei_command.py off          # 关水泵
    python test_huawei_command.py on 60        # 开水泵 60 秒
"""

import json
import sys
import time

from huaweicloudsdkcore.auth.credentials import BasicCredentials, DerivedCredentials
from huaweicloudsdkcore.region.region import Region as CoreRegion
# 显式导入需要的类，避免 import * 漏掉某些类
from huaweicloudsdkiotda.v5 import IoTDAClient
from huaweicloudsdkiotda.v5.model.create_command_request import CreateCommandRequest
from huaweicloudsdkiotda.v5.model.device_command_request import DeviceCommandRequest
from huaweicloudsdkiotda.v5.region.iotda_region import IoTDARegion

# ============================================================
#                      配置区
# ============================================================

# 目标设备（接收命令）
TARGET_DEVICE_ID = "6a17a638e094d61592419546_00001"

# SDK API 配置
HUAWEI_AK = "HPUAN1B4JPAKJJLLPWM1"
HUAWEI_SK = "hKbkdYNW61Lhtlu7Iphz7XIKaQUG1PRIrCb15kuX"
HUAWEI_PROJECT_ID = "16512cefc56d4bbc9cff96234619b8aa"
HUAWEI_REGION = "cn-east-3"
HUAWEI_ENDPOINT = "923924d24d.st1.iotda-app.cn-east-3.myhuaweicloud.com"
HUAWEI_INSTANCE_ID = "e01941fb-c614-415f-98cb-5d776280d89a"


# ============================================================
#                   SDK 命令下发
# ============================================================
def send_command(device_id: str, pump_on: bool, pump_time: int) -> bool:
    """
    通过华为云 SDK API 下发水泵控制命令

    参数:
        device_id:  目标设备 ID
        pump_on:    True=开泵, False=关泵
        pump_time:  开泵时长（秒），关泵时忽略
    """
    credentials = BasicCredentials(HUAWEI_AK, HUAWEI_SK, HUAWEI_PROJECT_ID) \
        .with_derived_predicate(DerivedCredentials.get_default_derived_predicate())

    client = IoTDAClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(CoreRegion(id=HUAWEI_REGION, endpoint=HUAWEI_ENDPOINT)) \
        .build()

    try:
        actual_time = pump_time if pump_on else 0

        request = CreateCommandRequest()
        request.device_id = device_id
        request.instance_id = HUAWEI_INSTANCE_ID
        request.body = DeviceCommandRequest(
            service_id="openWater",
            command_name="openWater",
            paras={"time": actual_time},
        )
        response = client.create_command(request)
        print(f"[SDK] 命令下发成功!")
        print(f"  command_id: {response.command_id}")
        print(f"  service_id: openWater")
        print(f"  command_name: openWater")
        print(f"  paras: {{\"time\": {actual_time}}}")
        return True
    except Exception as e:
        print(f"[SDK] 命令下发失败: {e}")
        return False


# ============================================================
#                     主流程
# ============================================================
def main():
    action   = "on"
    duration = 30

    if len(sys.argv) > 1:
        arg1 = sys.argv[1].lower()
        if arg1 in ("on", "off"):
            action = arg1
        else:
            print(f"用法: python test_huawei_command.py [on|off] [duration_seconds]")
            sys.exit(1)

    if len(sys.argv) > 2:
        try:
            duration = int(sys.argv[2])
        except ValueError:
            print(f"时长必须是数字: {sys.argv[2]}")
            sys.exit(1)

    if action == "off":
        duration = 0

    print()
    print("=" * 60)
    print("  华为云 IoTDA SDK 命令下发测试")
    print("=" * 60)
    print(f"  目标设备: {TARGET_DEVICE_ID}")
    print(f"  命令: pump={'ON' if action == 'on' else 'OFF'}, duration={duration}s")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    pump_on = (action == "on")
    success = send_command(TARGET_DEVICE_ID, pump_on, duration)

    print()
    print("=" * 60)
    if success:
        if pump_on:
            print(f"  开泵 {duration} 秒命令已下发，设备将在 {duration} 秒后自动关泵")
        else:
            print("  关泵命令已下发")
    else:
        print("  命令下发失败，请检查网络和配置")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
