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

    ESP8266 上报的 MQTT 消息格式：
    {
        "temperature": 28.5,
        "humidity": 65.0,
        "soil_moisture": 25.0,
        "pump_status": false,
        "wifi_signal": -65,
        "firmware_version": "1.0.0"
    }
    """
    try:
        body = await request.json()
        logger.info(f"收到华为云转发数据: {json.dumps(body, ensure_ascii=False)}")

        # 华为云 IoTDA 转发的数据格式
        # body 中包含 device_id 和 body（设备上报的原始数据）
        device_id = body.get("device_id") or body.get("deviceId", "unknown")
        payload = body.get("body") or body.get("message") or body

        # 如果 payload 是字符串，尝试解析 JSON
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                pass

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="数据格式错误")

        async with AsyncSessionLocal() as db:
            await process_sensor_data(db, device_id, payload)
            await db.commit()

        return {"success": True}

    except Exception as e:
        logger.error(f"处理IoT数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat")
async def device_heartbeat(request: Request):
    """设备心跳接口，用于检测设备在线状态"""
    try:
        body = await request.json()
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

        return {"success": True}
    except Exception as e:
        logger.error(f"心跳处理失败: {e}")
        return {"success": False}
