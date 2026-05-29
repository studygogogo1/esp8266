#!/usr/bin/env python3
"""
快速测试：通过华为云 SDK 下发 openWater 命令
用法: python test_sdk_command.py [time_seconds]
"""
import sys
import json

from huaweicloudsdkcore.auth.credentials import BasicCredentials, DerivedCredentials
from huaweicloudsdkcore.region.region import Region as CoreRegion
from huaweicloudsdkiotda.v5 import *
from huaweicloudsdkiotda.v5.region.iotda_region import IoTDARegion

# 配置
AK = "HPUAN1B4JPAKJJLLPWM1"
SK = "hKbkdYNW61Lhtlu7Iphz7XIKaQUG1PRIrCb15kuX"
PROJECT_ID = "16512cefc56d4bbc9cff96234619b8aa"
REGION = "cn-east-3"
ENDPOINT = "923924d24d.st1.iotda-app.cn-east-3.myhuaweicloud.com"
INSTANCE_ID = "e01941fb-c614-415f-98cb-5d776280d89a"
DEVICE_ID = "6a17a638e094d61592419546_00001"

# 开泵时长（秒），0 = 关泵
pump_time = int(sys.argv[1]) if len(sys.argv) > 1 else 3

print(f"目标设备: {DEVICE_ID}")
print(f"命令: openWater, time={pump_time}s")
print()

# 初始化 SDK
credentials = BasicCredentials(AK, SK, PROJECT_ID) \
    .with_derived_predicate(DerivedCredentials.get_default_derived_predicate())

client = IoTDAClient.new_builder() \
    .with_credentials(credentials) \
    .with_region(CoreRegion(id=REGION, endpoint=ENDPOINT)) \
    .build()

# 下发命令
request = CreateCommandRequest()
request.device_id = DEVICE_ID
request.instance_id = INSTANCE_ID
request.body = DeviceCommandRequest(
    service_id="openWater",
    command_name="openWater",
    paras={"time": pump_time},
)

try:
    response = client.create_command(request)
    print("✅ 命令下发成功!")
    print(f"   command_id: {response.command_id}")
    print(f"   response  : {response.response}")
    print(f"   error_code: {response.error_code}")
    print(f"   error_msg : {response.error_msg}")
except Exception as e:
    print(f"❌ 命令下发失败: {e}")
