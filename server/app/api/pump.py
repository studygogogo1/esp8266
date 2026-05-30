"""
水泵操作记录 API
从 sensor_data 表查询 pump_status 变化记录，无需单独建表
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.sensor import SensorData

router = APIRouter(prefix="/pump", tags=["水泵操作记录"])
logger = logging.getLogger(__name__)


@router.get("/{device_id}/logs")
async def get_pump_logs(
    device_id: str,
    days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db)
):
    """
    从 sensor_data 表查询水泵状态变化记录
    返回 pump_status 有值的记录，按时间倒序
    """
    since = datetime.now() - timedelta(days=days)
    result = await db.execute(
        select(SensorData)
        .where(
            SensorData.device_id == device_id,
            SensorData.created_at >= since,
            SensorData.pump_status.isnot(None),
        )
        .order_by(desc(SensorData.created_at))
        .limit(200)
    )
    records = result.scalars().all()

    # 从记录中提取状态变化（过滤掉连续相同状态的记录）
    logs = []
    for r in reversed(records):  # 按时间正序
        time = r.event_time.isoformat() if r.event_time else (r.created_at.isoformat() if r.created_at else None)
        logs.append({
            "id": r.id,
            "action": "on" if r.pump_status else "off",
            "source": "device",
            "time": r.created_at.isoformat() if r.created_at else None,
            "event_time": r.event_time.isoformat() if r.event_time else None,
        })

    return {
        "device_id": device_id,
        "days": days,
        "total": len(logs),
        "logs": logs,
    }
