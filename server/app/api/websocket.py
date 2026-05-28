"""
WebSocket 实时推送端点
App 通过 WebSocket 连接此端点，接收实时传感器数据和告警
"""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket import ws_manager

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    App 连接 WebSocket 实时接收数据
    
    消息格式：
    {
        "type": "sensor_update",  // 传感器数据更新
        "device_id": "device_001",
        "data": {
            "temperature": 28.5,
            "humidity": 65.0,
            "soil_moisture": 25.0,
            "pump_status": false,
            "timestamp": "2026-05-28T10:00:00"
        }
    }
    
    {
        "type": "alert",          // 告警
        "device_id": "device_001",
        "alert": {
            "type": "soil_dry",
            "message": "土壤过干: 20%",
            "value": 20.0,
            "threshold": 30.0
        }
    }
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # 等待客户端消息（心跳或其他指令）
            data = await websocket.receive_text()
            # 可以处理 App 发来的消息，比如心跳 ping
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("App WebSocket 断开连接")
