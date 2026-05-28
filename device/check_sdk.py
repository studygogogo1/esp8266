#!/usr/bin/env python3
"""
华为云IoTDA SDK 结构检查工具
- 自动检测可用的类
- 不依赖特定导入
"""

import sys

print("=" * 70)
print("  华为云IoTDA SDK 结构检查")
print("=" * 70)
print()

# 1. 导入SDK
print("[1/4] 导入华为云SDK...")
try:
    from huaweicloudsdkcore.auth.credentials import BasicCredentials
    from huaweicloudsdkiotda.v5 import *
    from huaweicloudsdkcore.region.region import Region
    print("  ✓ SDK导入成功")
except ImportError as e:
    print(f"  ❌ 导入失败: {e}")
    sys.exit(1)

print()

# 2. 检查 IoTDAClient 是否可用
print("[2/4] 检查 IoTDAClient...")
try:
    client = IoTDAClient.new_builder()
    print("  ✓ IoTDAClient 可用")
except Exception as e:
    print(f"  ❌ IoTDAClient 不可用: {e}")
    sys.exit(1)

print()

# 3. 查找包含 "Command" 的类
print("[3/4] 查找包含 'Command' 的类...")
current_module = sys.modules[__name__]

# 获取所有全局变量
all_vars = globals()

# 过滤出包含 Command 的类
command_classes = []
for name, obj in all_vars.items():
    if 'Command' in name and isinstance(obj, type):
        command_classes.append(name)

if command_classes:
    print(f"  找到 {len(command_classes)} 个类:")
    for cls in command_classes:
        print(f"    - {cls}")
else:
    print("  ⚠️  未找到包含 'Command' 的类")
    print("  所有全局变量（前30个）:")
    for i, name in enumerate(sorted(all_vars.keys())):
        if not name.startswith('_') and i < 30:
            print(f"    - {name}")

print()

# 4. 特别检查 CreateCommandRequest
print("[4/4] 检查 CreateCommandRequest...")
try:
    req = CreateCommandRequest()
    print("  ✓ CreateCommandRequest 可用")
    print("  - 属性列表:")
    for attr in dir(req):
        if not attr.startswith('_'):
            print(f"    - {attr}")
except Exception as e:
    print(f"  ❌ CreateCommandRequest 不可用: {e}")

print()
print("=" * 70)
print("  检查结果")
print("=" * 70)
print()
print("请根据上面的输出，告诉我:")
print("  1. 是否找到包含 'Command' 的类？")
print("  2. CreateCommandRequest 有哪些属性？")
print("     - 如果有 'body'，body 应该是什么类型？")
print()
