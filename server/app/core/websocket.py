import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器，用于向 App 推送实时数据"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 新连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket 断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息给所有连接的 App 客户端"""
        if not self.active_connections:
            return
        data = json.dumps(message, ensure_ascii=False)
        dead = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception:
                dead.add(connection)
        for conn in dead:
            self.active_connections.discard(conn)


# 全局连接管理器
ws_manager = ConnectionManager()
