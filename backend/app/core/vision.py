# 将应用配置转换为图纸视觉提取客户端，提取后的事实仍由业务层校验。
from __future__ import annotations

import json

from app.core.config import Settings
from app.drawing.extraction_client import VisionJsonClient


# 合并额外请求参数和思考开关，再传入模型、超时与重试配置。
def build_vision_client(settings: Settings) -> VisionJsonClient:
    extra_body = {}
    if settings.vision_extra_body:
        extra_body = json.loads(settings.vision_extra_body)
    if settings.vision_enable_thinking is False:
        extra_body.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
    return VisionJsonClient(
        base_url=settings.vision_binding_host,
        api_key=settings.vision_binding_api_key,
        model=settings.vision_model,
        timeout=settings.ai_request_timeout,
        max_retries=settings.ai_max_retries,
        extra_body=extra_body,
    )
