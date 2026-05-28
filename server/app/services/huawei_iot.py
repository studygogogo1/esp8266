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
from huaweicloudsdkcore.region.region import Region as CoreRegion
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
            .with_region(CoreRegion(id=settings.HUAWEI_REGION, endpoint=self.endpoint)) \
            .build()

    async def send_command(self, device_id: str, command: dict) -> bool:
        """
        向设备下发消息
        command 示例: {"pump": "on"} 或 {"pump": "off"}
        """
        try:
            # ===== 详细日志：记录下发的命令 =====
            logger.info("=" * 80)
            logger.info(f"[命令下发] 开始下发命令")
            logger.info(f"[命令下发] device_id: {device_id}")
            logger.info(f"[命令下发] command: {json.dumps(command, ensure_ascii=False)}")

            # 构造请求
            request = CreateMessageRequest()
            request.device_id = device_id
            request.instance_id = self.instance_id

            message_id = f"cmd_{int(time.time())}"
            request.body = CreateMessageRequestMessage(
                message_id=message_id,
                name="pump_control",
                message=json.dumps(command),
                encoding="none"
            )

            logger.info(f"[命令下发] message_id: {message_id}")
            logger.info(f"[命令下发] name: pump_control")
            logger.info(f"[命令下发] encoding: none")

            # 发送请求
            logger.info(f"[命令下发] 正在调用华为云 API...")
            response = self.client.create_message(request)

            # 记录响应
            logger.info(f"[命令下发] [OK] 命令下发成功!")
            logger.info(f"[命令下发] response.message_id: {response.message_id}")
            logger.info(f"[命令下发] response: {response.to_dict() if response else None}")
            logger.info("=" * 80)

            return True

        except exceptions.ClientRequestException as e:
            logger.error(f"[命令下发] [FAIL] 华为云 API 调用失败")
            logger.error(f"[命令下发] status_code: {e.status_code}")
            logger.error(f"[命令下发] error_code: {e.error_code}")
            logger.error(f"[命令下发] error_msg: {e.error_msg}")
            logger.error("=" * 80)
            return False

        except Exception as e:
            logger.error(f"[命令下发] [FAIL] 未知异常: {e}")
            logger.error(f"[命令下发] 异常类型: {type(e).__name__}")
            logger.error("=" * 80)
            return False

    async def get_device_shadow(self, device_id: str) -> Optional[dict]:
        """获取设备影子（设备当前状态缓存）"""
        try:
            logger.info(f"[设备影子] 正在获取设备 {device_id} 的影子...")

            request = ShowDeviceShadowRequest()
            request.device_id = device_id
            request.instance_id = self.instance_id

            response = self.client.show_device_shadow(request)

            if response:
                shadow_dict = response.to_dict()
                logger.info(f"[设备影子] [OK] 获取成功: {json.dumps(shadow_dict, ensure_ascii=False)}")
                return shadow_dict
            else:
                logger.warning(f"[设备影子] [WARN] 响应为空")
                return None

        except exceptions.ClientRequestException as e:
            logger.error(f"[设备影子] [FAIL] 华为云 API 调用失败")
            logger.error(f"[设备影子] status_code: {e.status_code}")
            logger.error(f"[设备影子] error_code: {e.error_code}")
            logger.error(f"[设备影子] error_msg: {e.error_msg}")
            return None

        except Exception as e:
            logger.error(f"[设备影子] [FAIL] 未知异常: {e}")
            logger.error(f"[设备影子] 异常类型: {type(e).__name__}")
            return None

    async def list_devices(self) -> list:
        """列出所有设备"""
        try:
            logger.info(f"[设备列表] 正在获取设备列表...")

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

            logger.info(f"[设备列表] [OK] 获取到 {len(device_list)} 个设备")
            for dev in device_list:
                logger.info(f"[设备列表]   - {dev['device_id']} | {dev['status']}")

            return device_list

        except exceptions.ClientRequestException as e:
            logger.error(f"[设备列表] [FAIL] 华为云 API 调用失败")
            logger.error(f"[设备列表] status_code: {e.status_code}")
            logger.error(f"[设备列表] error_code: {e.error_code}")
            logger.error(f"[设备列表] error_msg: {e.error_msg}")
            return []

        except Exception as e:
            logger.error(f"[设备列表] [FAIL] 未知异常: {e}")
            logger.error(f"[设备列表] 异常类型: {type(e).__name__}")
            return []


# 全局服务实例
huawei_iot = HuaweiIoTService()
