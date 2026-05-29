"""
数据处理服务
负责：
1. 处理设备上报的传感器数据
2. 存储到数据库
3. 触发告警检查
4. 触发自动控制规则
"""
import json
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor import SensorData
from app.models.device import Device
from app.models.alert import Alert, AlertRule
from app.models.rule import AutoRule

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

    # 日志：打印收到的原始数据
    logger.info("=" * 80)
    logger.info(f"[数据处理] 收到设备 {device_id} 的数据:")
    logger.info(f"[数据处理] 原始 data 对象: {json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else data}")
    logger.info(f"[数据处理] 解析结果: temp={temperature}, humi={humidity}, soil={soil_moisture}, pump={pump_status}")
    logger.info("=" * 80)

    # 1. 存储传感器历史数据
    sensor_record = SensorData(
        device_id=device_id,
        temperature=temperature,
        humidity=humidity,
        soil_moisture=soil_moisture,
        pump_status=pump_status,
    )
    db.add(sensor_record)

    # 2. 更新设备最新状态
    result = await db.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()

    if device:
        device.is_online = True
        device.last_online = datetime.now()
        # 只在数据中确实包含对应字段时才更新，避免 command_response 等非传感器消息用 None 覆盖已有有效值
        if temperature is not None:
            device.last_temperature = temperature
        if humidity is not None:
            device.last_humidity = humidity
        if soil_moisture is not None:
            device.last_soil_moisture = soil_moisture
        if pump_status is not None or "pump_status" in data:
            device.pump_status = pump_status
        if wifi_signal is not None:
            device.wifi_signal = wifi_signal
        if firmware_version is not None:
            device.firmware_version = firmware_version
    else:
        # 首次见到这个设备，自动注册（新设备允许 None 值）
        device = Device(
            device_id=device_id,
            is_online=True,
            last_online=datetime.now(),
            last_temperature=temperature,
            last_humidity=humidity,
            last_soil_moisture=soil_moisture,
            pump_status=pump_status if pump_status is not None else False,
            wifi_signal=wifi_signal,
            firmware_version=firmware_version or "1.0.0",
        )
        db.add(device)
        logger.info(f"新设备自动注册: {device_id}")

    await db.flush()

    # 3. 检查告警规则
    await check_alert_rules(db, device_id, temperature, humidity, soil_moisture)

    # 4. 检查自动控制规则（如土壤湿度低则自动浇水）
    await check_auto_rules(db, device_id, temperature, humidity, soil_moisture)

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
            logger.warning(f"告警触发: {message}")


async def check_auto_rules(db: AsyncSession, device_id: str,
                            temperature, humidity, soil_moisture):
    """检查自动控制规则"""
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
            from app.services.huawei_iot import huawei_iot
            await huawei_iot.send_command(device_id, {
                "pump": "on",
                "duration": rule.action_duration
            })
