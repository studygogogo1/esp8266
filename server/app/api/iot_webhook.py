"""
华为云 IoTDA 数据接收 API
华为云通过规则引擎将设备数据 HTTP 转发到此接口

安全机制：
华为云规则引擎转发时会自动在请求头带上 timestamp/nonce/signature，
服务端使用约定的 Token 验证签名，防止伪造请求。
"""
import hashlib
import json
import logging

from fastapi import APIRouter, Request, HTTPException
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.data_processor import process_sensor_data

router = APIRouter(prefix="/iot", tags=["IoT数据接收"])
logger = logging.getLogger(__name__)


def _verify_webhook_signature(request: Request) -> bool:
    """
    验证华为云规则引擎 HTTP 转发的签名

    华为云推送请求头包含三个字段：
    - timestamp: 平台推送时的时间戳
    - nonce: 平台生成的随机数
    - signature: SHA256(token + timestamp + nonce 字典排序后)

    参考：https://support.huaweicloud.com/usermanual-iothub/iot_01_0001.html
    """
    timestamp = request.headers.get("timestamp")
    nonce = request.headers.get("nonce")
    signature = request.headers.get("signature")

    # 缺少任一字段 → 拒绝
    if not all([timestamp, nonce, signature]):
        logger.warning(f"[签名校验] 缺少签名头: timestamp={timestamp}, nonce={nonce}, signature={signature}")
        return False

    token = settings.IOT_WEBHOOK_TOKEN

    # 将 token、timestamp、nonce 按字典序排序后拼接
    parts = sorted([token, timestamp, nonce])
    sorted_str = "".join(parts)

    # SHA256 哈希
    expected = hashlib.sha256(sorted_str.encode("utf-8")).hexdigest()

    if signature != expected:
        logger.warning(f"[签名校验] 签名不匹配, expected={expected[:16]}..., got={signature[:16]}...")
        return False

    return True


@router.post("/data")
async def receive_iot_data(request: Request):
    """
    华为云 IoTDA 规则引擎 HTTP 转发接口
    ESP8266 上报数据后，华为云自动 POST 到此接口

    华为云转发的数据格式（可能有两种）：
    格式1 - 规则引擎直接转发设备上报数据：
    {
        "temperature": 22.5,
        "humidity": 55.0,
        ...
    }

    格式2 - 规则引擎包装后的格式：
    {
        "device_id": "xxx",
        "timestamp": 1234567890,
        "body": {
            "temperature": 22.5,
            ...
        }
    }

    格式3 - 华为云标准转发格式：
    {
        "resource": "device.property",
        "from": "device_id",
        "event_time": "2026-05-29T01:29:27Z",
        "body": {
            "services": [...]
        }
    }
    """
    # ===== 签名校验 =====
    if not _verify_webhook_signature(request):
        logger.error("[IoT接收] 签名校验失败，拒绝请求")
        raise HTTPException(status_code=401, detail="签名校验失败")

    try:
        # 读取原始请求体
        raw_body = await request.body()
        logger.info("=" * 80)
        logger.info("[IoT接收] 收到华为云转发请求 (签名校验通过)")

        # 记录请求头
        headers = dict(request.headers)
        logger.info(f"[IoT接收] 请求头: {json.dumps(headers, ensure_ascii=False, indent=2)}")

        # 记录原始 body（字符串形式）
        try:
            raw_text = raw_body.decode('utf-8')
            logger.info(f"[IoT接收] 原始请求体 (RAW):\n{raw_text}")
        except Exception as e:
            logger.warning(f"[IoT接收] 原始请求体解码失败: {e}")
            logger.info(f"[IoT接收] 原始请求体 (bytes): {raw_body}")

        # 解析 JSON
        body = None
        try:
            if 'raw_text' in locals():
                body = json.loads(raw_text)
            else:
                body = await request.json()
        except json.JSONDecodeError as e:
            logger.error(f"[IoT接收] [FAIL] JSON 解析失败: {e}")
            logger.error(f"[IoT接收] 原始数据: {raw_body}")
            raise HTTPException(status_code=400, detail="JSON 格式错误")
        except Exception as e:
            logger.error(f"[IoT接收] [FAIL] 解析异常: {e}")
            body = await request.json()

        logger.info(f"[IoT接收] 解析后的 JSON (美观格式):\n{json.dumps(body, ensure_ascii=False, indent=2)}")
        logger.info(f"[IoT接收] 数据类型: {type(body)}")
        logger.info(f"[IoT接收] JSON 键列表: {list(body.keys()) if isinstance(body, dict) else 'Not a dict'}")

        # ===== 解析 device_id =====
        device_id = None

        if isinstance(body, dict):
            device_id = (
                body.get("device_id") or
                body.get("deviceId") or
                body.get("from")
            )

            if not device_id and "notify_data" in body:
                header = body.get("notify_data", {}).get("header", {})
                device_id = header.get("device_id") or header.get("deviceId")
                logger.info(f"[IoT接收] 从 notify_data.header 解析 device_id: {device_id}")

            if not device_id and "topic" in body:
                topic = body.get("topic", "")
                if "/devices/" in topic:
                    try:
                        device_id = topic.split("/devices/")[1].split("/")[0]
                        logger.info(f"[IoT接收] 从 topic 解析 device_id: {device_id}")
                    except Exception:
                        pass

            if not device_id and "services" in body:
                services = body.get("services", [])
                if services and isinstance(services[0], dict):
                    device_id = services[0].get("deviceId") or services[0].get("device_id")
                    logger.info(f"[IoT接收] 从 services[0] 解析 device_id: {device_id}")

        if not device_id:
            logger.warning("[IoT接收] [WARN] 无法从 body 中获取 device_id")
            device_id = "unknown"

        logger.info(f"[IoT接收] 解析 device_id: {device_id}")

        # ===== 解析 payload =====
        payload = None

        if isinstance(body, dict) and "notify_data" in body:
            notify_data = body.get("notify_data", {})
            notify_body = notify_data.get("body", {})
            services = notify_body.get("services", [])

            if services and isinstance(services[0], dict):
                properties = services[0].get("properties", {})
                if isinstance(properties, dict):
                    payload = properties
                    logger.info("[IoT接收] 数据格式: 华为云 notify_data 格式，已提取 properties")
                    logger.info(f"[IoT接收] 提取的 properties: {json.dumps(payload, ensure_ascii=False)}")
                else:
                    payload = services[0]
                    logger.info("[IoT接收] 数据格式: 华为云 notify_data 格式，使用 services[0]")
            else:
                payload = body
                logger.warning("[IoT接收] [WARN] notify_data 格式但未找到 services，使用原始 body")

        elif isinstance(body, dict) and "services" in body:
            payload = body
            logger.info("[IoT接收] 数据格式: 直接包含 services（华为云标准格式）")

        elif isinstance(body, dict) and "body" in body:
            payload = body["body"]
            logger.info("[IoT接收] 数据格式: 包装在 body 字段中")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                    logger.info("[IoT接收] payload 字符串已解析为 JSON")
                except Exception as e:
                    logger.warning(f"[IoT接收] [WARN] payload 字符串解析失败: {e}")

        elif isinstance(body, dict) and "message" in body:
            payload = body["message"]
            logger.info("[IoT接收] 数据格式: 包装在 message 字段中")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception as e:
                    logger.warning(f"[IoT接收] [WARN] message 解析失败: {e}")

        else:
            payload = body
            logger.info("[IoT接收] 数据格式: 直接是设备数据（扁平格式）")

        logger.info(f"[IoT接收] 解析后的 payload: {json.dumps(payload, ensure_ascii=False)}")
        logger.info(f"[IoT接收] payload 类型: {type(payload)}")

        if not isinstance(payload, dict):
            logger.error(f"[IoT接收] [FAIL] payload 不是 dict: {type(payload)}")
            raise HTTPException(status_code=400, detail="数据格式错误：payload 不是 JSON 对象")

        # ===== 处理数据 =====
        logger.info(f"[IoT接收] 开始处理数据: device_id={device_id}")
        async with AsyncSessionLocal() as db:
            await process_sensor_data(db, device_id, payload)
            await db.commit()
            logger.info(f"[IoT接收] [OK] 数据已保存到数据库")

        logger.info("=" * 80)

        return {"success": True, "message": "数据接收成功"}

    except json.JSONDecodeError as e:
        logger.error(f"[IoT接收] [FAIL] JSON 解析失败: {e}")
        raise HTTPException(status_code=400, detail="JSON 格式错误")

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[IoT接收] [FAIL] 处理失败: {e}", exc_info=True)
        logger.error(f"[IoT接收] 错误类型: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat")
async def device_heartbeat(request: Request):
    """设备心跳接口，用于检测设备在线状态"""
    try:
        body = await request.json()
        logger.info(f"[心跳] 收到心跳: {json.dumps(body, ensure_ascii=False)}")

        device_id = body.get("device_id", "unknown")

        from datetime import datetime
        from sqlalchemy import select
        from app.models.device import Device
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Device).where(Device.device_id == device_id))
            device = result.scalar_one_or_none()
            if device:
                device.is_online = True
                device.last_online = datetime.now()
                await db.commit()
                logger.info(f"[心跳] [OK] 设备 {device_id} 心跳更新成功")
            else:
                logger.warning(f"[心跳] [WARN] 设备 {device_id} 不存在")

        return {"success": True}
    except Exception as e:
        logger.error(f"[心跳] [FAIL] 处理失败: {e}", exc_info=True)
        return {"success": False}
