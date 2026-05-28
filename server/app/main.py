"""
FastAPI 主应用入口
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db
from app.api import devices, sensor, pump, alerts, rules, firmware, iot_webhook, websocket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭生命周期"""
    logger.info("服务器启动中...")
    await init_db()
    logger.info("数据库初始化完成")
    yield
    logger.info("服务器关闭")


app = FastAPI(
    title="ESP8266 IoT 控制平台",
    description="ESP8266 物联网设备管理平台 - 支持传感器数据采集、水泵远程控制、OTA升级",
    version="1.0.0",
    lifespan=lifespan,
)

# 跨域配置（允许 App 访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(iot_webhook.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(sensor.router, prefix="/api")
app.include_router(pump.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(firmware.router, prefix="/api")
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {
        "name": "ESP8266 IoT 控制平台",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}
