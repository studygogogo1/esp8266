from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 服务器配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-this-secret-key"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./iot_data.db"

    # 华为云 IoTDA
    HUAWEI_ACCESS_KEY: str = "HPUAN1B4JPAKJJLLPWM1"
    HUAWEI_SECRET_KEY: str = "hKbkdYNW61Lhtlu7Iphz7XIKaQUG1PRIrCb15kuX"
    HUAWEI_REGION: str = "cn-east-3"
    HUAWEI_PROJECT_ID: str = "16512cefc56d4bbc9cff96234619b8aa"
    HUAWEI_ENDPOINT: str = "923924d24d.st1.iotda-app.cn-east-3.myhuaweicloud.com"
    HUAWEI_IOTDA_INSTANCE_ID: str = "e01941fb-c614-415f-98cb-5d776280d89a"

    # 华为云规则引擎 HTTP 转发签名 Token
    # 在华为云创建规则引擎转发目标时，填入此 Token
    IOT_WEBHOOK_TOKEN: str = "e4ef6da527ec5461b69a52fa558af908"

    # OTA
    FIRMWARE_DIR: str = "./firmware"
    RELEASES_DIR: str = "./releases"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
