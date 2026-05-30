from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class Alert(Base):
    """告警记录表"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True)
    alert_type = Column(String(32), comment="类型: temp_high/temp_low/humidity_low/soil_dry/offline")
    value = Column(Float, nullable=True, comment="触发时的实际值")
    threshold = Column(Float, nullable=True, comment="告警阈值")
    message = Column(String(256))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, index=True)
    event_time = Column(DateTime, nullable=True, comment="设备采集时间(关联的传感器数据event_time)")


class AlertRule(Base):
    """告警规则配置表"""
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True)
    rule_type = Column(String(32), comment="temp_high/temp_low/humidity_low/soil_dry")
    threshold = Column(Float, nullable=False)
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
