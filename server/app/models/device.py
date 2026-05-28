from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.sql import func
from app.core.database import Base


class Device(Base):
    """设备表 - 存储设备信息和最新状态"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), unique=True, index=True, nullable=False)
    device_name = Column(String(128), default="我的ESP8266")
    is_online = Column(Boolean, default=False)
    last_online = Column(DateTime, nullable=True)
    wifi_signal = Column(Integer, nullable=True, comment="WiFi信号强度(dBm)")
    firmware_version = Column(String(32), default="1.0.0")

    # 最新传感器值（冗余存储，方便快速查询）
    last_temperature = Column(Float, nullable=True)
    last_humidity = Column(Float, nullable=True)
    last_soil_moisture = Column(Float, nullable=True)
    pump_status = Column(Boolean, default=False, comment="水泵状态")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
