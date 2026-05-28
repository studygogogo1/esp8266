#!/usr/bin/env python3
"""
华为云IoTDA 命令下发测试脚本（独立版）
- 直接调用华为云SDK
- 不依赖后端服务
- 从 config.py 读取配置
- 使用方法: python3 test_huawei_command.py [on|off] [duration]
"""

import sys
import os
import time

# ========== 添加项目路径，导入config.py ==========
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

try:
    from app.core.config import settings
    print("✓ 从 config.py 读取配置")
except ImportError as e:
    print(f"❌ 无法导入 config.py: {e}")
    print("请确保:")
    print("  1. 在云端服务器上运行（已有config.py）")
    print("  2. 或者设置环境变量")
    sys.exit(1)

# ========== 从config.py读取配置 ==========
ACCESS_KEY = settings.HUAWEI_ACCESS_KEY
SECRET_KEY = settings.HUAWEI_SECRET_KEY
REGION = settings.HUAWEI_REGION
ENDPOINT = settings.HUAWEI_ENDPOINT
INSTANCE_ID = settings.HUAWEI_IOTDA_INSTANCE_ID
DEVICE_ID = "6a17a638e094d61592419546_00001"

# ========== 导入华为云SDK ==========
try:
    from huaweicloudsdkcore.auth.credentials import BasicCredentials
    from huaweicloudsdkiotda.v5 import IoTDAClient
    from huaweicloudsdkiotda.v5.model.create_command_request import CreateCommandRequest
    from huaweicloudsdkiotda.v5.model.command import Command
    from huaweicloudsdkcore.region.region import Region
    print("✓ 华为云SDK导入成功")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请先安装: pip3 install huaweicloudsdkcore huaweicloudsdkiotda")
    sys.exit(1)


def send_command(action: str = "on", duration: int = 30):
    """发送命令到设备"""
    print()
    print("=" * 70)
    print("  华为云IoTDA 命令下发测试")
    print("=" * 70)
    print()

    # 1. 初始化客户端
    print("[1/3] 初始化华为云客户端...")
    try:
        credentials = BasicCredentials(ACCESS_KEY, SECRET_KEY)
        client = IoTDAClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(Region(id=REGION, endpoint=ENDPOINT)) \
            .build()
        print("  ✓ 客户端初始化成功")
        print(f"  - Endpoint: {ENDPOINT}")
        print()
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        return False

    # 2. 构造命令
    print("[2/3] 构造命令...")
    try:
        command_id = f"test_{int(time.time())}"
        request = CreateCommandRequest()
        request.device_id = DEVICE_ID
        request.instance_id = INSTANCE_ID
        
        # 使用正确的 Command 类
        command = Command()
        command.command_id = command_id
        command.command_name = "pump_control"
        command.paras = [
            {"para_name": "pump", "para_value": action},
            {"para_name": "duration", "para_value": str(duration)}
        ]
        request.body = command

        print(f"  ✓ 命令ID: {command_id}")
        print(f"  ✓ 设备ID: {DEVICE_ID}")
        print(f"  ✓ 动作: {action}")
        print(f"  ✓ 时长: {duration}秒")
        print()
    except Exception as e:
        print(f"  ❌ 构造失败: {e}")
        return False

    # 3. 发送命令
    print("[3/3] 发送命令...")
    try:
        response = client.create_command(request)
        print("  ✓ 命令下发成功!")
        print(f"  - 响应命令ID: {response.command_id}")
        print()
        print("-" * 70)
        print("请检查设备是否收到命令:")
        print(f"  设备订阅的topic: $oc/devices/{DEVICE_ID}/sys/commands/#")
        print(f"  命令内容: pump={action}, duration={duration}")
        print("-" * 70)
        print()
        return True
    except Exception as e:
        print(f"  ❌ 下发失败: {e}")
        if hasattr(e, 'status_code'):
            print(f"  - 状态码: {e.status_code}")
        if hasattr(e, 'error_code'):
            print(f"  - 错误码: {e.error_code}")
        if hasattr(e, 'error_msg'):
            print(f"  - 错误信息: {e.error_msg}")
        print()
        return False


def main():
    # 解析命令行参数
    action = "on"
    duration = 30

    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ["on", "off"]:
            action = sys.argv[1].lower()
        else:
            print(f"未知参数: {sys.argv[1]}")
            print("用法: python3 test_huawei_command.py [on|off] [duration]")
            print("示例: python3 test_huawei_command.py on 30")
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
    print("🚀 开始测试...")
    print(f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    result = send_command(action, duration)

    print("=" * 70)
    if result:
        print("✅ 测试完成: 命令已下发，请检查设备!")
    else:
        print("❌ 测试失败: 命令下发失败!")
        print()
        print("可能的原因:")
        print("  1. 设备不在线 (请到华为云IoTDA控制台确认)")
        print("  2. 凭证错误 (请检查config.py)")
        print("  3. 网络问题 (请检查服务器能否访问华为云)")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
