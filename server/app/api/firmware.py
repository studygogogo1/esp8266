"""
OTA 固件升级 API
"""
import hashlib
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.models.firmware import Firmware

router = APIRouter(prefix="/firmware", tags=["OTA固件升级"])


@router.get("/latest")
async def get_latest_firmware(
    device_type: str = "esp8266",
    current_version: str = "",
    db: AsyncSession = Depends(get_db)
):
    """
    ESP8266 定期调用此接口检查是否有新版本
    返回最新版本信息
    """
    result = await db.execute(
        select(Firmware).where(
            Firmware.device_type == device_type,
            Firmware.is_latest == True
        )
    )
    firmware = result.scalar_one_or_none()

    if not firmware:
        return {"has_update": False}

    has_update = firmware.version != current_version

    return {
        "has_update": has_update,
        "version": firmware.version,
        "md5": firmware.md5,
        "file_size": firmware.file_size,
        "changelog": firmware.changelog,
    }


@router.get("/download/{version}")
async def download_firmware(version: str, db: AsyncSession = Depends(get_db)):
    """下载指定版本的固件"""
    result = await db.execute(select(Firmware).where(Firmware.version == version))
    firmware = result.scalar_one_or_none()

    if not firmware:
        raise HTTPException(status_code=404, detail="固件版本不存在")

    file_path = os.path.join(settings.FIRMWARE_DIR, firmware.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="固件文件不存在")

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=firmware.filename,
    )


class FirmwareUploadRequest(BaseModel):
    version: str
    changelog: str = ""
    device_type: str = "esp8266"
    set_as_latest: bool = True


@router.post("/upload")
async def upload_firmware(
    version: str,
    changelog: str = "",
    device_type: str = "esp8266",
    set_as_latest: bool = True,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """上传新固件（管理员接口）"""
    os.makedirs(settings.FIRMWARE_DIR, exist_ok=True)

    # 读取文件并计算 MD5
    content = await file.read()
    md5 = hashlib.md5(content).hexdigest()
    filename = f"firmware_{device_type}_{version}.bin"
    file_path = os.path.join(settings.FIRMWARE_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # 如果设为最新版本，先取消其他版本的 is_latest
    if set_as_latest:
        await db.execute(
            update(Firmware)
            .where(Firmware.device_type == device_type)
            .values(is_latest=False)
        )

    firmware = Firmware(
        version=version,
        filename=filename,
        file_size=len(content),
        md5=md5,
        changelog=changelog,
        device_type=device_type,
        is_latest=set_as_latest,
    )
    db.add(firmware)

    return {
        "success": True,
        "version": version,
        "md5": md5,
        "file_size": len(content),
        "message": f"固件 {version} 上传成功"
    }


@router.get("/list")
async def list_firmwares(db: AsyncSession = Depends(get_db)):
    """获取所有固件版本列表"""
    result = await db.execute(select(Firmware).order_by(Firmware.created_at.desc()))
    firmwares = result.scalars().all()
    return [
        {
            "version": f.version,
            "is_latest": f.is_latest,
            "device_type": f.device_type,
            "file_size": f.file_size,
            "md5": f.md5,
            "changelog": f.changelog,
            "created_at": f.created_at.isoformat(),
        }
        for f in firmwares
    ]
