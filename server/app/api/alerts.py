"""
告警 API
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import get_db
from app.models.alert import Alert, AlertRule

router = APIRouter(prefix="/alerts", tags=["告警管理"])


class AlertRuleRequest(BaseModel):
    rule_type: str   # temp_high / temp_low / humidity_low / soil_dry
    threshold: float
    enabled: bool = True


@router.get("/{device_id}/list")
async def get_alerts(
    device_id: str,
    days: int = Query(default=7),
    unread_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db)
):
    """获取告警记录列表"""
    since = datetime.now() - timedelta(days=days)
    query = select(Alert).where(
        Alert.device_id == device_id,
        Alert.created_at >= since
    )
    if unread_only:
        query = query.where(Alert.is_read == False)
    query = query.order_by(desc(Alert.created_at)).limit(100)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return {
        "count": len(alerts),
        "alerts": [
            {
                "id": a.id,
                "type": a.alert_type,
                "message": a.message,
                "value": a.value,
                "threshold": a.threshold,
                "is_read": a.is_read,
                "time": a.created_at.isoformat(),
                "event_time": a.event_time.isoformat() if a.event_time else None,
            }
            for a in alerts
        ]
    }


@router.post("/{device_id}/read/{alert_id}")
async def mark_alert_read(device_id: str, alert_id: int, db: AsyncSession = Depends(get_db)):
    """标记告警为已读"""
    await db.execute(
        update(Alert).where(Alert.id == alert_id).values(is_read=True)
    )
    return {"success": True}


@router.get("/{device_id}/rules")
async def get_alert_rules(device_id: str, db: AsyncSession = Depends(get_db)):
    """获取告警规则配置"""
    result = await db.execute(select(AlertRule).where(AlertRule.device_id == device_id))
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "rule_type": r.rule_type,
            "threshold": r.threshold,
            "enabled": r.enabled,
        }
        for r in rules
    ]


@router.post("/{device_id}/rules")
async def upsert_alert_rule(
    device_id: str,
    req: AlertRuleRequest,
    db: AsyncSession = Depends(get_db)
):
    """新增或更新告警规则"""
    result = await db.execute(
        select(AlertRule).where(
            AlertRule.device_id == device_id,
            AlertRule.rule_type == req.rule_type
        )
    )
    rule = result.scalar_one_or_none()

    if rule:
        rule.threshold = req.threshold
        rule.enabled = req.enabled
    else:
        rule = AlertRule(
            device_id=device_id,
            rule_type=req.rule_type,
            threshold=req.threshold,
            enabled=req.enabled,
        )
        db.add(rule)

    return {"success": True, "message": "规则已保存"}
