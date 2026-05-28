"""
华为云 IoTDA 服务
负责：
1. 通过 AMQP 接收设备上报的传感器数据
2. 通过 HTTP API 下发控制指令给 ESP8266
"""
import json
import logging
import time
from typing import Optional

from huaweicloudsdkcore.auth.credentials import BasicCredentials, DerivedCredentials
from huaweicloudsdkcore.region.region import Region as coreRegion
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiotda.v5 import *
from huaweicloudsdkiotda.v5.region.iotda_region import IoTDARegion

from app.core.config import settings

logger = logging.getLogger(__name__)


class HuaweiIoTService:
    """华为云 IoTDA 服务封装"""

    def __init__(self):
        self.project_id = settings.HUAWEI_PROJECT_ID
        self.instance_id = settings.HUAWEI_IOTDA_INSTANCE_ID
        self.endpoint = settings.HUAWEI_ENDPOINT

        # 使用派生密钥（非基础版实例必须）
        credentials = BasicCredentials(
            settings.HUAWEI_ACCESS_KEY,
            settings.HUAWEI_SECRET_KEY
        ).with_derived_predicate(
            DerivedCredentials.get_default_derived_predicate()
        )

        self.client = IoTDAClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(coreRegion(id=settings.HUAWEI_REGION, endpoint=self.endpoint)) \
            .build()

    async def send_command(self, device_id: str, command: dict) -> bool:
        """
        向设备下发消息
        command 示例: {"pump": "on"} 或 {"pump": "off"}
        """
        try:
            request = CreateMessageRequest()
            request.device_id = device_id
            request.instance_id = self.instance_id
            request.body = CreateMessageRequestMessage(
                message_id=f"cmd_{int(time.time())}",
                name="pump_control",
                message=json.dumps(command),
                encoding="none"
            )
            response = self.client.create_message(request)
            logger.info(f"命令下发成功: device={device_id}, cmd={command}, msg_id={response.message_id}")
            return True
        except exceptions.ClientRequestException as e:
            logger.error(f"命令下发失败: {e.status_code} {e.error_code} {e.error_msg}")
            return False
        except Exception as e:
            logger.error(f"命令下发异常: {e}")
            return False

    async def get_device_shadow(self, device_id: str) -> Optional[dict]:
        """获取设备影子（设备当前状态缓存）"""
        try:
            request = ShowDeviceShadowRequest()
            request.device_id = device_id
            request.instance_id = self.instance_id
            response = self.client.show_device_shadow(request)
            return response.to_dict() if response else None
        except exceptions.ClientRequestException as e:
            logger.error(f"获取设备影子失败: {e.status_code} {e.error_code} {e.error_msg}")
        except Exception as e:
            logger.error(f"获取设备影子异常: {e}")
        return None

    async def list_devices(self) -> list:
        """列出所有设备"""
        try:
            request = ListDevicesRequest()
            request.instance_id = self.instance_id
            response = self.client.list_devices(request)
            devices = response.devices or []
            return [
                {
                    "device_id": d.device_id,
                    "device_name": d.device_name,
                    "status": d.status,
                    "last_online_time": d.last_online_time
                }
                for d in devices
            ]
        except exceptions.ClientRequestException as e:
            logger.error(f"列出设备失败: {e.status_code} {e.error_code} {e.error_msg}")
        except Exception as e:
            logger.error(f"列出设备异常: {e}")
        return []


# 全局服务实例
huawei_iot = HuaweiIoTService()
