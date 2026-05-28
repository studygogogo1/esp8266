"""
华为云 IoTDA 服务
负责：
1. 通过 AMQP 接收设备上报的传感器数据
2. 通过 HTTP API 下发控制指令给 ESP8266
"""
import json
import logging
import asyncio
import hashlib
import hmac
import time
from typing import Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


def _sign_request(ak: str, sk: str, method: str, uri: str, body: str = "") -> dict:
    """华为云 API 签名"""
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    date = timestamp[:8]

    signed_headers = "content-type;host;x-sdk-date"
    content_type = "application/json"
    host = settings.HUAWEI_ENDPOINT

    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = (
        f"{method}\n{uri}\n\n"
        f"content-type:{content_type}\nhost:{host}\nx-sdk-date:{timestamp}\n\n"
        f"{signed_headers}\n{body_hash}"
    )

    credential_scope = f"{date}/{settings.HUAWEI_REGION}/iotda/sdk_request"
    string_to_sign = (
        f"SDK-HMAC-SHA256\n{timestamp}\n{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    )

    def _hmac_sha256(key, msg):
        return hmac.new(key if isinstance(key, bytes) else key.encode("utf-8"),
                        msg.encode("utf-8"), hashlib.sha256).digest()

    signing_key = _hmac_sha256(
        _hmac_sha256(_hmac_sha256(_hmac_sha256(f"SDK{sk}", date), settings.HUAWEI_REGION),
                     "iotda"),
        "sdk_request"
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"SDK-HMAC-SHA256 Access={ak}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    return {
        "Content-Type": content_type,
        "Host": host,
        "X-Sdk-Date": timestamp,
        "Authorization": authorization,
    }


class HuaweiIoTService:
    """华为云 IoTDA 服务封装"""

    def __init__(self):
        self.base_url = f"https://{settings.HUAWEI_ENDPOINT}"
        self.project_id = settings.HUAWEI_PROJECT_ID
        self.ak = settings.HUAWEI_ACCESS_KEY
        self.sk = settings.HUAWEI_SECRET_KEY

    async def send_command(self, device_id: str, command: dict) -> bool:
        """
        向设备下发命令
        command 示例: {"pump": "on"} 或 {"pump": "off"}
        """
        uri = f"/v5/iot/{self.project_id}/devices/{device_id}/messages"
        body = json.dumps({
            "message_id": f"cmd_{int(time.time())}",
            "name": "pump_control",
            "message": json.dumps(command),
            "encoding": "none"
        })

        headers = _sign_request(self.ak, self.sk, "POST", uri, body)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}{uri}",
                    content=body,
                    headers=headers,
                    timeout=10
                )
                if resp.status_code in (200, 201):
                    logger.info(f"命令下发成功: device={device_id}, cmd={command}")
                    return True
                else:
                    logger.error(f"命令下发失败: {resp.status_code} {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"命令下发异常: {e}")
            return False

    async def get_device_shadow(self, device_id: str) -> Optional[dict]:
        """获取设备影子（设备当前状态缓存）"""
        uri = f"/v5/iot/{self.project_id}/devices/{device_id}/shadow"
        headers = _sign_request(self.ak, self.sk, "GET", uri)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}{uri}",
                    headers=headers,
                    timeout=10
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.error(f"获取设备影子失败: {e}")
        return None


# 全局服务实例
huawei_iot = HuaweiIoTService()
