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

        # 判断是标准版还是企业版
        # 标准版 endpoint 格式: xxxx.st1.iotda-app.region.myhuaweicloud.com
        # 企业版 endpoint 格式: iotda.region.myhuaweicloud.com
        is_standard = "st1.iotda-app" in self.endpoint

        if is_standard:
            # 标准版：使用基础认证，不需要 DerivedCredentials
            credentials = BasicCredentials(
                settings.HUAWEI_ACCESS_KEY,
                settings.HUAWEI_SECRET_KEY
            )
            logger.info("[华为云] 使用标准版认证（BasicCredentials）")
        else:
            # 企业版：使用派生认证
            credentials = BasicCredentials(
                settings.HUAWEI_ACCESS_KEY,
                settings.HUAWEI_SECRET_KEY
            ).with_derived_predicate(
                DerivedCredentials.get_default_derived_predicate()
            )
            logger.info("[华为云] 使用企业版认证（DerivedCredentials）")

        self.client = IoTDAClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(CoreRegion(id=settings.HUAWEI_REGION, endpoint=self.endpoint)) \
            .build()

        logger.info(f"[华为云] IoTDA 客户端初始化完成")
        logger.info(f"[华为云] endpoint: {self.endpoint}")
        logger.info(f"[华为云] instance_id: {self.instance_id}")

    async def send_command(self, device_id: str, command: dict) -> bool:
        """
        向设备下发消息（MQTT 消息下发）
        command 示例: {"pump": "on"} 或 {"pump": "off"}
        """
        try:
            # ===== 详细日志：记录下发的命令 =====
            logger.info("=" * 80)
            logger.info(f"[命令下发] 开始下发消息")
            logger.info(f"[命令下发] device_id: {device_id}")
            logger.info(f"[命令下发] command: {json.dumps(command, ensure_ascii=False)}")

            # 构造请求 - 使用 create_message API（消息下发）
            request = CreateMessageRequest()
            request.device_id = device_id
            request.instance_id = self.instance_id

            message_id = f"msg_{int(time.time())}"
            
            # 消息下发需要指定 topic（设备订阅的主题）
            # ESP8266 订阅的主题: $oc/devices/{device_id}/user/pump
            topic = f"$oc/devices/{device_id}/user/pump"
            
            request.body = CreateMessageRequestMessage(
                message_id=message_id,
                name="pump_control",
                message=json.dumps(command),
                topic=topic,
                encoding="none"
            )

            logger.info(f"[命令下发] message_id: {message_id}")
            logger.info(f"[命令下发] topic: {topic}")
            logger.info(f"[命令下发] message: {json.dumps(command)}")

            # 发送请求
            logger.info(f"[命令下发] 正在调用华为云 API...")
            response = self.client.create_message(request)

            # 记录响应
            logger.info(f"[命令下发] [OK] 消息下发成功!")
            logger.info(f"[命令下发] response.message_id: {response.message_id}")
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
