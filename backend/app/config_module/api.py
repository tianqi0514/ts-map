"""
系统配置模块 —— 独立于智谱、智脑
提供 LLM 配置管理、全局设置
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.llm_client import LLMClient
from app.schemas import ApiResponse

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/llm")
def get_llm_config() -> ApiResponse:
    """获取当前 LLM 配置（脱敏）"""
    settings = get_settings()
    key = settings.llm_api_key
    masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
    return ApiResponse(data={
        "api_key": masked_key,
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "configured": bool(key and settings.llm_base_url),
    })


@router.post("/llm/test")
def test_llm_connection() -> ApiResponse:
    """测试 LLM 连接是否可用"""
    client = LLMClient()
    if not client.is_available():
        return ApiResponse(data={"ok": False, "error": "LLM 未配置"})

    try:
        result = client.chat(
            messages=[
                {"role": "system", "content": "你是一个助手"},
                {"role": "user", "content": "请回复：连接成功"},
            ],
        )
        return ApiResponse(data={
            "ok": True,
            "response": result["content"][:100],
            "model": result["model"],
            "usage": result["usage"],
        })
    except Exception as e:
        return ApiResponse(data={"ok": False, "error": str(e)})


@router.get("/system")
def get_system_info() -> ApiResponse:
    """获取系统信息"""
    settings = get_settings()
    client = LLMClient()
    return ApiResponse(data={
        "llm": {
            "configured": client.is_available(),
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
        },
        "database": settings.database_url.replace("://", "://***@"),
        "neo4j": settings.neo4j_uri,
    })
