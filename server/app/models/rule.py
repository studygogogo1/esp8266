from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.sql import func
from app.core.database import Base


class AutoRule(Base):
    """自动控制规则表（如土壤湿度低于30%自动浇水）"""
    __tablename__ = "auto_rules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True)
    rule_name = Column(String(64), default="自动浇水")
    condition_type = Column(String(32), comment="soil_moisture/humidity/schedule")
    condition_operator = Column(String(8), comment="lt/gt/eq (小于/大于/等于)")
    condition_value = Column(Float, comment="触发条件值")
    action = Column(String(16), default="pump_on")
    action_duration = Column(Integer, default=30, comment="执行时长(秒)")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
