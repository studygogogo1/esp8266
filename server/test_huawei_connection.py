"""
华为云 IoTDA 连接测试
"""
import sys
sys.path.insert(0, ".")

import asyncio
import httpx
from app.services.huawei_iot import _sign_request, huawei_iot
from app.core.config import settings


async def test_list_devices():
    """测试1: 查询设备列表（验证签名+网络连通）"""
    print("=" * 60)
    print("测试1: 查询华为云 IoTDA 设备列表")
    print("=" * 60)

    uri = f"/v5/iot/{settings.HUAWEI_PROJECT_ID}/devices"
    headers = _sign_request(settings.HUAWEI_ACCESS_KEY, settings.HUAWEI_SECRET_KEY, "GET", uri)

    print(f"Endpoint: {settings.HUAWEI_ENDPOINT}")
    print(f"Project ID: {settings.HUAWEI_PROJECT_ID}")
    print(f"Region: {settings.HUAWEI_REGION}")
    print()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://{settings.HUAWEI_ENDPOINT}{uri}",
                headers=headers,
                timeout=15
            )
            print(f"HTTP 状态码: {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                devices = data.get("devices", [])
                print(f"✅ 连接成功！共找到 {len(devices)} 个设备")
                for d in devices:
                    print(f"   - 设备ID: {d.get('device_id')}")
                    print(f"     名称: {d.get('device_name')}")
                    print(f"     状态: {d.get('status')} (ONLINE=在线, OFFLINE=离线)")
                    print(f"     在线: {d.get('connection_status', 'UNKNOWN')}")
                    print()
                return True
            else:
                print(f"❌ 请求失败: {resp.text[:500]}")
                return False
    except httpx.ConnectError as e:
        print(f"❌ 网络连接失败: {e}")
        print("   可能原因: 网络不通、Endpoint 配置错误")
        return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


async def test_query_resources():
    """测试2: 查询项目资源（验证认证+API权限）"""
    print("=" * 60)
    print("测试2: 查询华为云 IoTDA 产品列表")
    print("=" * 60)

    uri = f"/v5/iot/{settings.HUAWEI_PROJECT_ID}/products"
    headers = _sign_request(settings.HUAWEI_ACCESS_KEY, settings.HUAWEI_SECRET_KEY, "GET", uri)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://{settings.HUAWEI_ENDPOINT}{uri}",
                headers=headers,
                timeout=15
            )
            print(f"HTTP 状态码: {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                products = data.get("products", [])
                print(f"✅ 认证成功！共找到 {len(products)} 个产品")
                for p in products:
                    print(f"   - 产品ID: {p.get('product_id')}")
                    print(f"     名称: {p.get('product_name')}")
                return True
            elif resp.status_code == 403:
                print(f"❌ 权限不足 (403): AK/SK 可能没有 IoTDA 权限")
                return False
            else:
                print(f"❌ 请求失败: {resp.text[:500]}")
                return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        return False


async def main():
    print()
    print("🔍 华为云 IoTDA 连接测试")
    print(f"目标地址: https://{settings.HUAWEI_ENDPOINT}")
    print()

    r1 = await test_list_devices()
    r2 = await test_query_resources()

    print()
    print("=" * 60)
    if r1 and r2:
        print("🎉 全部测试通过！华为云 IoTDA 连接正常")
    elif r1 or r2:
        print("⚠️  部分测试通过，请检查上面的错误信息")
    else:
        print("❌ 全部测试失败，连接存在问题")
        print()
        print("请检查:")
        print("  1. 网络是否能访问华为云 (ping 923924d24d.st1.iotda-device.cn-east-3.myhuaweicloud.com)")
        print("  2. AK/SK 是否正确且有效")
        print("  3. Project ID 是否正确")
        print("  4. 该 AK/SK 是否有 IoTDA 的权限")
    print("=" * 60)


asyncio.run(main())
