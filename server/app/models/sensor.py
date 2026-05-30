from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class SensorData(Base):
    """传感器数据表 - 存储温度、湿度、土壤湿度的历史记录"""
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), index=True, nullable=False)
    temperature = Column(Float, nullable=True, comment="温度(°C)")
    humidity = Column(Float, nullable=True, comment="空气湿度(%RH)")
    soil_moisture = Column(Float, nullable=True, comment="土壤湿度(%)")
    pump_status = Column(Boolean, nullable=True, comment="水泵状态(True=开/False=关)")
    created_at = Column(DateTime, index=True, comment="服务器接收时间(北京时间)")
    event_time = Column(DateTime, nullable=True, comment="设备采集时间(设备上报的event_time)")
