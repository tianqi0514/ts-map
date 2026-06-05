"""
LLM 客户端封装
支持小米米墨 API（OpenAI 兼容格式）
"""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.config import get_settings


class LLMClient:
    """LLM 客户端，封装 chat completions"""

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature

    def is_available(self) -> bool:
        return bool(self.client.api_key) and bool(self.client.base_url)

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
    ) -> dict[str, Any]:
        """
        发送聊天请求

        Args:
            messages: 消息列表，每个消息为 {"role": "user|system|assistant", "content": "..."}
            model: 覆盖默认模型
            temperature: 覆盖默认温度
            json_mode: 是否要求返回 JSON

        Returns:
            {"content": str, "usage": dict, "model": str}
        """
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": messages,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        return {
            "content": response.choices[0].message.content or "",
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            "model": response.model,
        }

    def generate_test_data(
        self,
        scene_description: str,
        connector_mappings: list[dict[str, Any]],
        ontology_objects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        根据自然语言场景描述，生成规则引擎测试数据

        Args:
            scene_description: 用户描述，如"一份150万的采购合同，等待法务审批"
            connector_mappings: 连接器字段映射列表
            ontology_objects: 本体对象定义列表

        Returns:
            {"test_data": dict, "scene_summary": str}
        """
        # 构建提示
        mapping_desc = "\n".join([
            f"- {m['source_field']} ({m['transform']}) → 对象: {m['target_code']}"
            for m in connector_mappings[:20]
        ])

        system_prompt = """你是一个企业业务数据生成助手。
根据用户描述的场景和系统定义的字段映射，生成符合结构的 JSON 测试数据。

要求：
1. 只返回 JSON 对象，不要任何解释
2. JSON 必须符合字段映射的结构（对象.字段）
3. 数据要真实合理（合同编号、金额、日期等）
4. 根据用户描述的"异常场景"生成对应的数据（如金额超限、缺少审批等）"""

        user_prompt = f"""场景描述：{scene_description}

可用字段映射：
{mapping_desc}

请生成一段 JSON 测试数据，格式要求：
{{
  "contract": {{"contractNo": "...", "amount": ..., "status": "..."}},
  "party": {{"name": "...", "creditScore": ...}},
  ...
}}
"""

        result = self.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            json_mode=True,
        )

        try:
            test_data = json.loads(result["content"])
            # 如果 LLM 返回了包裹的 test_data 字段，提取它
            if "test_data" in test_data and isinstance(test_data["test_data"], dict):
                test_data = test_data["test_data"]
            return {
                "test_data": test_data,
                "scene_summary": scene_description,
                "model": result["model"],
                "usage": result["usage"],
            }
        except json.JSONDecodeError:
            return {
                "test_data": {},
                "scene_summary": scene_description,
                "error": "LLM 返回了非 JSON 内容",
                "raw": result["content"],
            }


def get_llm_client() -> LLMClient:
    return LLMClient()
