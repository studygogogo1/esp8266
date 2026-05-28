"""
反推华为云 IoTDA 的 HMAC 密码生成规则
通过已知的预生成密码反推正确的算法
"""

import hmac
import hashlib
import base64
from datetime import datetime, timezone

DEVICE_SECRET = "Cyy542100312"
TIMESTAMP = "2026052814"
KNOWN_PASSWORD = "c45d75f6216842a052a5c8f38408195d0a5f0e6fcab40c291390f45b7ec5dfeb"

print("=" * 60)
print("  反推华为云 IoTDA HMAC-SHA256 密码生成规则")
print("=" * 60)
print(f"  DeviceSecret:  {DEVICE_SECRET}")
print(f"  Timestamp:     {TIMESTAMP}")
print(f"  已知密码(预生成): {KNOWN_PASSWORD}")
print("=" * 60)

# 尝试各种可能的组合
combinations = [
    ("HMAC(secret, timestamp)",       DEVICE_SECRET, TIMESTAMP),
    ("HMAC(timestamp, secret)",       TIMESTAMP,       DEVICE_SECRET),
    ("HMAC(secret, timestamp+secret)", DEVICE_SECRET, TIMESTAMP + DEVICE_SECRET),
    ("HMAC(timestamp+secret, secret)", TIMESTAMP + DEVICE_SECRET, DEVICE_SECRET),
    ("HMAC(secret+timestamp, secret)", DEVICE_SECRET + TIMESTAMP, DEVICE_SECRET),
    ("HMAC(secret, DeviceID)",         DEVICE_SECRET, "6a17a638e094d61592419546_00001"),
    ("HMAC(DeviceID, secret)",         "6a17a638e094d61592419546_00001", DEVICE_SECRET),
    ("HMAC(DeviceID+timestamp, secret)","6a17a638e094d61592419546_00001" + TIMESTAMP, DEVICE_SECRET),
    ("HMAC(secret, DeviceID+timestamp)",DEVICE_SECRET, "6a17a638e094d61592419546_00001" + TIMESTAMP),
    ("HMAC(secret, timestamp+DeviceID)",DEVICE_SECRET, TIMESTAMP + "6a17a638e094d61592419546_00001"),
]

found = False
for desc, key, msg in combinations:
    sig = hmac.new(key.encode(), msg.encode(), hashlib.sha256).digest()
    pwd_b64 = base64.b64encode(sig).decode()
    pwd_hex = sig.hex()
    match_b64 = pwd_b64 == KNOWN_PASSWORD
    match_hex = pwd_hex == KNOWN_PASSWORD
    if match_b64 or match_hex:
        print(f"\n*** 匹配成功! ***")
        print(f"  方式: {desc}")
        print(f"  Key:  {key}")
        print(f"  Msg:  {msg}")
        print(f"  密码: {pwd_b64}")
        print(f"  编码: {'Base64' if match_b64 else 'Hex'}")
        found = True
    else:
        print(f"  [{desc}] -> {pwd_b64[:24]}... (不匹配)")

if not found:
    print("\n--- 没有匹配的组合，尝试更多变体 ---")
    # 尝试带分隔符的
    more = [
        ("HMAC(secret, timestamp\\n)",  DEVICE_SECRET, TIMESTAMP + "\n"),
        ("HMAC(secret, timestamp\\0)",   DEVICE_SECRET, TIMESTAMP + "\0"),
        ("HMAC(DeviceID_0_0_timestamp, secret)", "6a17a638e094d61592419546_00001_0_0_" + TIMESTAMP, DEVICE_SECRET),
        ("HMAC(secret, DeviceID_0_0_timestamp)", DEVICE_SECRET, "6a17a638e094d61592419546_00001_0_0_" + TIMESTAMP),
    ]
    for desc, key, msg in more:
        sig = hmac.new(key.encode(), msg.encode(), hashlib.sha256).digest()
        pwd_b64 = base64.b64encode(sig).decode()
        match = pwd_b64 == KNOWN_PASSWORD
        if match:
            print(f"\n*** 匹配成功! ***")
            print(f"  方式: {desc}")
            print(f"  密码: {pwd_b64}")
            found = True
        else:
            print(f"  [{desc}] -> {pwd_b64[:24]}... (不匹配)")

if not found:
    print("\n所有常见组合都不匹配，密码可能是通过华为云在线工具预生成的固定值")
