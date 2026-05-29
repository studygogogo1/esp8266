"""
华为云 IoTDA 服务
负责：
1. 通过 SDK API 下发控制指令给 ESP8266（CreateCommand）
2. 通过 SDK API 管理设备列表、设备影子等

设备数据接收走 HTTP 转发通道：POST /api/iot/data（iot_webhook.py）
"""

import logging
from typing import Optional

from huaweicloudsdkcore.auth.credentials import BasicCredentials, DerivedCredentials
from huaweicloudsdkcore.region.region import Region as CoreRegion
from huaweicloudsdkiotda.v5 import *
from huaweicloudsdkiotda.v5.region.iotda_region import IoTDARegion

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
#              HuaweiIoTService（SDK 管理 API）
# ============================================================
class HuaweiIoTService:
    """华为云 IoTDA SDK 服务封装（命令下发 + 设备管理）"""

    def __init__(self):
        self.project_id = settings.HUAWEI_PROJECT_ID
        self.instance_id = settings.HUAWEI_IOTDA_INSTANCE_ID
        self.endpoint = settings.HUAWEI_ENDPOINT

        credentials = BasicCredentials(
            settings.HUAWEI_ACCESS_KEY,
            settings.HUAWEI_SECRET_KEY
        ).with_derived_predicate(
            DerivedCredentials.get_default_derived_predicate()
        )

        self.client = IoTDAClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(CoreRegion(id=settings.HUAWEI_REGION, endpoint=self.endpoint)) \
            .build()

        logger.info(f"[华为云SDK] 客户端初始化完成, endpoint={self.endpoint}")

    # -------- 命令下发（通过 SDK API）--------
    async def send_command(self, device_id: str, command: dict) -> bool:
        """
        通过华为云 SDK API 向设备下发命令（CreateCommand 同步命令）

        命令格式匹配产品模型：
        - service_id = "openWater"
        - command_name = "openWater"
        - paras = {"time": N}   N>0 开泵 N 秒, N=0 关泵

        Args:
            device_id: 目标设备ID
            command: 命令字典，如 {"pump": "on", "duration": 30}
                     内部转换为 openWater 产品模型格式
        """
        try:
            pump_action = command.get("pump", "off")
            duration    = command.get("duration", 0)
            pump_time   = duration if pump_action == "on" else 0

            request = CreateCommandRequest()
            request.device_id = device_id
            request.instance_id = self.instance_id
            request.body = DeviceCommandRequest(
                service_id="openWater",
                command_name="openWater",
                paras={"time": pump_time},
            )

            response = self.client.create_command(request)
            logger.info(f"[命令下发] 成功 → {device_id}, time={pump_time}s, command_id={response.command_id}")
            return True
        except Exception as e:
            logger.error(f"[命令下发] 失败: {e}")
            return False

    async def get_device_shadow(self, device_id: str) -> Optional[dict]:
        """获取设备影子（设备当前状态缓存）"""
        try:
            request = ShowDeviceShadowRequest()
            request.device_id = device_id
            request.instance_id = self.instance_id
            response = self.client.show_device_shadow(request)
            if response:
                logger.info(f"[设备影子] 获取成功: {device_id}")
                return response.to_dict()
            return None
        except Exception as e:
            logger.error(f"[设备影子] 失败: {e}")
            return None

    async def list_devices(self) -> list:
        """列出所有设备"""
        try:
            request = ListDevicesRequest()
            request.instance_id = self.instance_id
            response = self.client.list_devices(request)
            devices = response.devices or []
            device_list = [
                {
                    "device_id": d.device_id,
                    "device_name": d.device_name,
                    "status": d.status,
                    "last_online_time": d.last_online_time
                }
                for d in devices
            ]
            logger.info(f"[设备列表] 获取到 {len(device_list)} 个设备")
            return device_list
        except Exception as e:
            logger.error(f"[设备列表] 失败: {e}")
            return []


# ============================================================
#              全局实例
# ============================================================

# SDK 服务实例（命令下发 + 设备管理）
huawei_iot = HuaweiIoTService()
