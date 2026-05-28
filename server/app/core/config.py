from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 服务器配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-this-secret-key"
    DEBUG: bool = True

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"

    # 华为云 IoTDA（从环境变量读取，不要硬编码！）
    HUAWEI_ACCESS_KEY: Optional[str] = None
    HUAWEI_SECRET_KEY: Optional[str] = None
    HUAWEI_REGION: str = "cn-east-3"
    HUAWEI_PROJECT_ID: Optional[str] = None
    HUAWEI_ENDPOINT: Optional[str] = None
    HUAWEI_IOTDA_INSTANCE_ID: Optional[str] = None

    # OTA
    FIRMWARE_DIR: str = "./firmware"
    RELEASES_DIR: str = "./releases"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
