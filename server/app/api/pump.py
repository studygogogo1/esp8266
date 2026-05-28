"""
水泵操作记录 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.pump import PumpLog

router = APIRouter(prefix="/pump", tags=["水泵记录"])


@router.get("/{device_id}/logs")
async def get_pump_logs(
    device_id: str,
    days: int = Query(default=7, ge=1, le=90, description="查询最近多少天"),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db)
):
    """获取水泵操作历史记录"""
    since = datetime.now() - timedelta(days=days)
    result = await db.execute(
        select(PumpLog)
        .where(PumpLog.device_id == device_id, PumpLog.created_at >= since)
        .order_by(desc(PumpLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()

    return {
        "device_id": device_id,
        "days": days,
        "count": len(logs),
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "source": log.source,
                "duration": log.duration,
                "time": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }
