"""
设备相关 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.device import Device
from app.services.huawei_iot import huawei_iot

router = APIRouter(prefix="/devices", tags=["设备管理"])


class DeviceResponse(BaseModel):
    device_id: str
    device_name: str
    is_online: bool
    last_temperature: Optional[float]
    last_humidity: Optional[float]
    last_soil_moisture: Optional[float]
    pump_status: bool
    wifi_signal: Optional[int]
    firmware_version: str
    last_online: Optional[str]

    class Config:
        from_attributes = True


class PumpControlRequest(BaseModel):
    action: str  # "on" 或 "off"
    duration: Optional[int] = 30  # 开泵持续时长（秒），关泵时忽略


@router.post("/sync")
async def sync_devices_from_huawei(db: AsyncSession = Depends(get_db)):
    """从华为云 IoTDA 同步设备列表到本地数据库"""
    try:
        # 从华为云获取设备列表
        huawei_devices = await huawei_iot.list_devices()

        synced_count = 0
        for hd in huawei_devices:
            # 检查设备是否已存在
            result = await db.execute(
                select(Device).where(Device.device_id == hd["device_id"])
            )
            device = result.scalar_one_or_none()

            if device:
                # 更新现有设备
                device.device_name = hd.get("device_name", device.device_name)
                device.is_online = (hd.get("status") == "online")
                if hd.get("last_online_time"):
                    from datetime import datetime
                    device.last_online = datetime.fromtimestamp(hd["last_online_time"] / 1000)
            else:
                # 创建新设备
                device = Device(
                    device_id=hd["device_id"],
                    device_name=hd.get("device_name", ""),
                    is_online=(hd.get("status") == "online"),
                    last_temperature=None,
                    last_humidity=None,
                    last_soil_moisture=None,
                    pump_status=False,
                    wifi_signal=None,
                    firmware_version="1.0.0"
                )
                if hd.get("last_online_time"):
                    from datetime import datetime
                    device.last_online = datetime.fromtimestamp(hd["last_online_time"] / 1000)
                db.add(device)

            synced_count += 1

        await db.commit()
        return {"success": True, "message": f"成功同步 {synced_count} 个设备"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/", response_model=list[DeviceResponse])
async def list_devices(db: AsyncSession = Depends(get_db)):
    """获取所有设备列表"""
    result = await db.execute(select(Device))
    devices = result.scalars().all()
    return [DeviceResponse(
        device_id=d.device_id,
        device_name=d.device_name,
        is_online=d.is_online,
        last_temperature=d.last_temperature,
        last_humidity=d.last_humidity,
        last_soil_moisture=d.last_soil_moisture,
        pump_status=d.pump_status,
        wifi_signal=d.wifi_signal,
        firmware_version=d.firmware_version,
        last_online=d.last_online.isoformat() if d.last_online else None,
    ) for d in devices]


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个设备详情"""
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return DeviceResponse(
        device_id=device.device_id,
        device_name=device.device_name,
        is_online=device.is_online,
        last_temperature=device.last_temperature,
        last_humidity=device.last_humidity,
        last_soil_moisture=device.last_soil_moisture,
        pump_status=device.pump_status,
        wifi_signal=device.wifi_signal,
        firmware_version=device.firmware_version,
        last_online=device.last_online.isoformat() if device.last_online else None,
    )


@router.post("/{device_id}/pump")
async def control_pump(
    device_id: str,
    req: PumpControlRequest,
    db: AsyncSession = Depends(get_db)
):
    """控制水泵开关"""
    from app.models.pump import PumpLog

    if req.action not in ("on", "off"):
        raise HTTPException(status_code=400, detail="action 只能是 on 或 off")

    # 下发指令到设备
    command = {"pump": req.action}
    if req.action == "on":
        command["duration"] = req.duration

    success = await huawei_iot.send_command(device_id, command)
    if not success:
        raise HTTPException(status_code=502, detail="指令下发失败，请检查设备是否在线")

    # 记录操作日志
    pump_log = PumpLog(
        device_id=device_id,
        action=req.action,
        source="app",
        duration=req.duration if req.action == "on" else None,
    )
    db.add(pump_log)

    return {"success": True, "message": f"水泵已{'开启' if req.action == 'on' else '关闭'}"}
