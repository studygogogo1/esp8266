"""
传感器历史数据 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.sensor import SensorData

router = APIRouter(prefix="/sensor", tags=["传感器数据"])


class SensorRecord(BaseModel):
    id: int
    device_id: str
    temperature: Optional[float]
    humidity: Optional[float]
    soil_moisture: Optional[float]
    created_at: str

    class Config:
        from_attributes = True


@router.get("/{device_id}/history")
async def get_sensor_history(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=720, description="查询最近多少小时的数据"),
    limit: int = Query(default=200, ge=1, le=1000, description="最多返回条数"),
    db: AsyncSession = Depends(get_db)
):
    """获取传感器历史数据，用于 App 绘制曲线图"""
    since = datetime.now() - timedelta(hours=hours)
    result = await db.execute(
        select(SensorData)
        .where(SensorData.device_id == device_id, SensorData.created_at >= since)
        .order_by(desc(SensorData.created_at))
        .limit(limit)
    )
    records = result.scalars().all()

    return {
        "device_id": device_id,
        "hours": hours,
        "count": len(records),
        "data": [
            {
                "id": r.id,
                "temperature": r.temperature,
                "humidity": r.humidity,
                "soil_moisture": r.soil_moisture,
                "pump_status": r.pump_status,
                "time": r.created_at.isoformat() if r.created_at else None,
                "event_time": r.event_time.isoformat() if r.event_time else None,
            }
            for r in reversed(records)  # 按时间正序返回
        ]
    }


@router.get("/{device_id}/stats")
async def get_sensor_stats(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db)
):
    """获取传感器统计数据（最高/最低/平均值）"""
    since = datetime.now() - timedelta(hours=hours)
    result = await db.execute(
        select(
            func.avg(SensorData.temperature).label("avg_temp"),
            func.max(SensorData.temperature).label("max_temp"),
            func.min(SensorData.temperature).label("min_temp"),
            func.avg(SensorData.humidity).label("avg_humi"),
            func.avg(SensorData.soil_moisture).label("avg_soil"),
        )
        .where(SensorData.device_id == device_id, SensorData.created_at >= since)
    )
    row = result.first()

    return {
        "device_id": device_id,
        "hours": hours,
        "temperature": {
            "avg": round(row.avg_temp, 1) if row.avg_temp else None,
            "max": round(row.max_temp, 1) if row.max_temp else None,
            "min": round(row.min_temp, 1) if row.min_temp else None,
        },
        "humidity": {
            "avg": round(row.avg_humi, 1) if row.avg_humi else None,
        },
        "soil_moisture": {
            "avg": round(row.avg_soil, 1) if row.avg_soil else None,
        }
    }
