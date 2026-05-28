"""
FastAPI 主应用入口
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.database import init_db
from app.api import devices, sensor, pump, alerts, rules, firmware, iot_webhook, websocket

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

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


# 静态文件挂载（JS/CSS/图片等，如果需要）
# 注意：必须放在路由注册之前，否则会覆盖 / 路由
# 这里不挂载根路径，而是手动在 root() 中返回 HTML


@app.get("/")
async def root():
    """Web 管理页面"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
async def health_check():
    return {"status": "ok"}
