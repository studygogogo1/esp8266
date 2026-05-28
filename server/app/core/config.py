from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 服务器配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-this-secret-key"
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./iot_data.db"

    # 华为云 IoTDA
    HUAWEI_ACCESS_KEY: str = "HPUAH0WAJF9MUXFC5OGY"
    HUAWEI_SECRET_KEY: str = "EqWRye9LONyY0zMQeIFQDfjS4vnYVyVkApFEJyIq"
    HUAWEI_REGION: str = "cn-east-3"
    HUAWEI_PROJECT_ID: str = "16512cefc56d4bbc9cff96234619b8aa"
    HUAWEI_ENDPOINT: str = "923924d24d.st1.iotda-device.cn-east-3.myhuaweicloud.com"

    # OTA
    FIRMWARE_DIR: str = "./firmware"
    RELEASES_DIR: str = "./releases"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
