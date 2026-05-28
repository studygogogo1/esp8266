from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.sql import func
from app.core.database import Base


class PumpLog(Base):
    """水泵操作记录表"""
    __tablename__ = "pump_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True, nullable=False)
    action = Column(String(8), nullable=False, comment="on/off")
    source = Column(String(16), default="app", comment="操作来源: app/auto/device")
    duration = Column(Integer, nullable=True, comment="运行时长(秒)")
    created_at = Column(DateTime, server_default=func.now(), index=True)
