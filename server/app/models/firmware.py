from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class Firmware(Base):
    """固件版本管理表（OTA）"""
    __tablename__ = "firmware"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(32), unique=True, nullable=False)
    filename = Column(String(128), nullable=False)
    file_size = Column(Integer)
    md5 = Column(String(64))
    changelog = Column(String(512))
    is_latest = Column(Boolean, default=False)
    device_type = Column(String(32), default="esp8266")
    created_at = Column(DateTime, server_default=func.now())
