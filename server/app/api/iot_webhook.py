"""
华为云 IoTDA 数据接收 API
华为云通过规则引擎将设备数据 HTTP 转发到此接口
"""

import json
import logging

from fastapi import APIRouter, Request, HTTPException
from app.core.database import AsyncSessionLocal
from app.services.data_processor import process_sensor_data

router = APIRouter(prefix="/iot", tags=["IoT数据接收"])
logger = logging.getLogger(__name__)


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
    try:
        # ===== 详细日志：记录收到的所有信息 =====
        body = await request.json()

        # 记录请求头
        headers = dict(request.headers)
        logger.info("=" * 80)
        logger.info("[IoT接收] 收到华为云转发请求")
        logger.info(f"[IoT接收] 请求头: {json.dumps(headers, ensure_ascii=False)}")

        # 记录原始 body
        logger.info(f"[IoT接收] 原始数据: {json.dumps(body, ensure_ascii=False)}")
        logger.info(f"[IoT接收] 数据类型: {type(body)}")

        # ===== 解析 device_id =====
        device_id = None

        # 尝试从不同字段获取 device_id
        if isinstance(body, dict):
            device_id = (
                body.get("device_id") or
                body.get("deviceId") or
                body.get("from") or
                body.get("deviceId_str")
            )

        if not device_id:
            # 如果 body 里有 services，尝试从 topic 或其他地方获取
            logger.warning("[IoT接收] [WARN] 无法从 body 中获取 device_id")
            device_id = "unknown"

        logger.info(f"[IoT接收] 解析 device_id: {device_id}")

        # ===== 解析 payload（设备上报的数据）=====
        payload = None

        # 情况1：body 直接是设备上报的数据
        if isinstance(body, dict) and "services" in body:
            payload = body
            logger.info("[IoT接收] 数据格式: 直接包含 services（华为云标准格式）")

        # 情况2：body 里有 body 字段
        elif isinstance(body, dict) and "body" in body:
            payload = body["body"]
            logger.info("[IoT接收] 数据格式: 包装在 body 字段中")

            # 如果 payload 是字符串，尝试解析 JSON
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                    logger.info("[IoT接收] payload 字符串已解析为 JSON")
                except Exception as e:
                    logger.warning(f"[IoT接收] [WARN] payload 字符串解析失败: {e}")

        # 情况3：body 里有 message 字段
        elif isinstance(body, dict) and "message" in body:
            payload = body["message"]
            logger.info("[IoT接收] 数据格式: 包装在 message 字段中")

            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception as e:
                    logger.warning(f"[IoT接收] [WARN] message 解析失败: {e}")

        # 情况4：body 直接是设备数据（扁平格式）
        else:
            payload = body
            logger.info("[IoT接收] 数据格式: 直接是设备数据（扁平格式）")

        logger.info(f"[IoT接收] 解析后的 payload: {json.dumps(payload, ensure_ascii=False)}")
        logger.info(f"[IoT接收] payload 类型: {type(payload)}")

        # ===== 验证 payload =====
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
