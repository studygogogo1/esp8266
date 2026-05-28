"""
数据处理服务
负责：
1. 处理设备上报的传感器数据
2. 存储到数据库
3. 触发告警检查
4. 触发自动控制规则
5. 推送 WebSocket 实时消息给 App
"""
import logging
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor import SensorData
from app.models.device import Device
from app.models.pump import PumpLog
from app.models.alert import Alert, AlertRule
from app.models.rule import AutoRule
from app.core.websocket import ws_manager

logger = logging.getLogger(__name__)


async def process_sensor_data(db: AsyncSession, device_id: str, data: dict):
    """
    处理传感器上报数据
    data 格式: {
        "temperature": 28.5,
        "humidity": 65.0,
        "soil_moisture": 25.0,
        "pump_status": false,
        "wifi_signal": -65,
        "firmware_version": "1.0.0"
    }
    """
    temperature = data.get("temperature")
    humidity = data.get("humidity")
    soil_moisture = data.get("soil_moisture")
    pump_status = data.get("pump_status", False)
    wifi_signal = data.get("wifi_signal")
    firmware_version = data.get("firmware_version", "1.0.0")

    # 1. 存储传感器历史数据
    sensor_record = SensorData(
        device_id=device_id,
        temperature=temperature,
        humidity=humidity,
        soil_moisture=soil_moisture,
    )
    db.add(sensor_record)

    # 2. 更新设备最新状态
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()

    if device:
        device.is_online = True
        device.last_online = datetime.now()
        device.last_temperature = temperature
        device.last_humidity = humidity
        device.last_soil_moisture = soil_moisture
        device.pump_status = pump_status
        device.wifi_signal = wifi_signal
        device.firmware_version = firmware_version
    else:
        # 首次见到这个设备，自动注册
        device = Device(
            device_id=device_id,
            is_online=True,
            last_online=datetime.now(),
            last_temperature=temperature,
            last_humidity=humidity,
            last_soil_moisture=soil_moisture,
            pump_status=pump_status,
            wifi_signal=wifi_signal,
            firmware_version=firmware_version,
        )
        db.add(device)
        logger.info(f"新设备自动注册: {device_id}")

    await db.flush()

    # 3. 检查告警规则
    await check_alert_rules(db, device_id, temperature, humidity, soil_moisture)

    # 4. 检查自动控制规则（如土壤湿度低则自动浇水）
    await check_auto_rules(db, device_id, temperature, humidity, soil_moisture)

    # 5. 推送实时数据给 App（WebSocket）
    await ws_manager.broadcast({
        "type": "sensor_update",
        "device_id": device_id,
        "data": {
            "temperature": temperature,
            "humidity": humidity,
            "soil_moisture": soil_moisture,
            "pump_status": pump_status,
            "wifi_signal": wifi_signal,
            "timestamp": datetime.now().isoformat(),
        }
    })

    logger.info(f"数据处理完成: device={device_id}, temp={temperature}, humi={humidity}, soil={soil_moisture}")


async def check_alert_rules(db: AsyncSession, device_id: str,
                             temperature, humidity, soil_moisture):
    """检查告警规则，触发则创建告警记录"""
    result = await db.execute(
        select(AlertRule).where(AlertRule.device_id == device_id, AlertRule.enabled == True)
    )
    rules = result.scalars().all()

    for rule in rules:
        value = None
        triggered = False
        message = ""

        if rule.rule_type == "temp_high" and temperature is not None:
            value = temperature
            if temperature > rule.threshold:
                triggered = True
                message = f"温度过高: {temperature}°C (阈值: {rule.threshold}°C)"

        elif rule.rule_type == "temp_low" and temperature is not None:
            value = temperature
            if temperature < rule.threshold:
                triggered = True
                message = f"温度过低: {temperature}°C (阈值: {rule.threshold}°C)"

        elif rule.rule_type == "humidity_low" and humidity is not None:
            value = humidity
            if humidity < rule.threshold:
                triggered = True
                message = f"空气湿度过低: {humidity}% (阈值: {rule.threshold}%)"

        elif rule.rule_type == "soil_dry" and soil_moisture is not None:
            value = soil_moisture
            if soil_moisture < rule.threshold:
                triggered = True
                message = f"土壤过干: {soil_moisture}% (阈值: {rule.threshold}%)"

        if triggered:
            alert = Alert(
                device_id=device_id,
                alert_type=rule.rule_type,
                value=value,
                threshold=rule.threshold,
                message=message,
            )
            db.add(alert)
            # 推送告警给 App
            await ws_manager.broadcast({
                "type": "alert",
                "device_id": device_id,
                "alert": {
                    "type": rule.rule_type,
                    "message": message,
                    "value": value,
                    "threshold": rule.threshold,
                }
            })
            logger.warning(f"告警触发: {message}")


async def check_auto_rules(db: AsyncSession, device_id: str,
                            temperature, humidity, soil_moisture):
    """检查自动控制规则"""
    from app.services.huawei_iot import huawei_iot
    from app.core.database import AsyncSessionLocal

    result = await db.execute(
        select(AutoRule).where(AutoRule.device_id == device_id, AutoRule.enabled == True)
    )
    rules = result.scalars().all()

    for rule in rules:
        value = None
        if rule.condition_type == "soil_moisture":
            value = soil_moisture
        elif rule.condition_type == "humidity":
            value = humidity

        if value is None:
            continue

        triggered = False
        if rule.condition_operator == "lt" and value < rule.condition_value:
            triggered = True
        elif rule.condition_operator == "gt" and value > rule.condition_value:
            triggered = True
        elif rule.condition_operator == "eq" and value == rule.condition_value:
            triggered = True

        if triggered and rule.action == "pump_on":
            logger.info(f"自动规则触发: {rule.rule_name}, 自动开泵 {rule.action_duration}秒")
            # 下发开泵指令
            await huawei_iot.send_command(device_id, {
                "pump": "on",
                "duration": rule.action_duration
            })
            # 记录水泵日志
            pump_log = PumpLog(
                device_id=device_id,
                action="on",
                source="auto",
                duration=rule.action_duration,
            )
            db.add(pump_log)
