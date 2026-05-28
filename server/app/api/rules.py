"""
自动控制规则 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.rule import AutoRule

router = APIRouter(prefix="/rules", tags=["自动控制规则"])


class AutoRuleRequest(BaseModel):
    rule_name: str = "自动浇水"
    condition_type: str   # soil_moisture / humidity
    condition_operator: str  # lt / gt
    condition_value: float
    action: str = "pump_on"
    action_duration: int = 30
    enabled: bool = True


@router.get("/{device_id}")
async def get_rules(device_id: str, db: AsyncSession = Depends(get_db)):
    """获取设备的自动控制规则"""
    result = await db.execute(select(AutoRule).where(AutoRule.device_id == device_id))
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "rule_name": r.rule_name,
            "condition": f"{r.condition_type} {'<' if r.condition_operator == 'lt' else '>'} {r.condition_value}",
            "condition_type": r.condition_type,
            "condition_operator": r.condition_operator,
            "condition_value": r.condition_value,
            "action": r.action,
            "action_duration": r.action_duration,
            "enabled": r.enabled,
        }
        for r in rules
    ]


@router.post("/{device_id}")
async def create_rule(
    device_id: str,
    req: AutoRuleRequest,
    db: AsyncSession = Depends(get_db)
):
    """创建自动控制规则"""
    rule = AutoRule(
        device_id=device_id,
        rule_name=req.rule_name,
        condition_type=req.condition_type,
        condition_operator=req.condition_operator,
        condition_value=req.condition_value,
        action=req.action,
        action_duration=req.action_duration,
        enabled=req.enabled,
    )
    db.add(rule)
    await db.flush()
    return {"success": True, "id": rule.id, "message": "规则创建成功"}


@router.put("/{device_id}/{rule_id}")
async def update_rule(
    device_id: str,
    rule_id: int,
    req: AutoRuleRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新自动控制规则"""
    result = await db.execute(
        select(AutoRule).where(AutoRule.id == rule_id, AutoRule.device_id == device_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    rule.rule_name = req.rule_name
    rule.condition_type = req.condition_type
    rule.condition_operator = req.condition_operator
    rule.condition_value = req.condition_value
    rule.action = req.action
    rule.action_duration = req.action_duration
    rule.enabled = req.enabled

    return {"success": True, "message": "规则更新成功"}


@router.delete("/{device_id}/{rule_id}")
async def delete_rule(device_id: str, rule_id: int, db: AsyncSession = Depends(get_db)):
    """删除自动控制规则"""
    result = await db.execute(
        select(AutoRule).where(AutoRule.id == rule_id, AutoRule.device_id == device_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    await db.delete(rule)
    return {"success": True, "message": "规则已删除"}
