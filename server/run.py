"""
服务器启动入口
运行方式：python run.py
"""
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,  # 部署时关闭热重载
        log_level="info",
    )
