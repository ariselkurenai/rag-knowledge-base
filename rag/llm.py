"""LLM 客户端：DeepSeek Chat（同步 / 流式 / JSON 模式）"""

import json
import logging
from typing import Generator, Optional

from .config import settings

logger = logging.getLogger(__name__)


class ChatLLM:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None,
                 base_url: Optional[str] = None, temperature: Optional[float] = None):
        from openai import OpenAI

        self.model = model or settings.chat_model
        self.temperature = settings.temperature if temperature is None else temperature
        self.client = OpenAI(
            api_key=api_key or settings.deepseek_api_key,
            base_url=base_url or settings.deepseek_api_base,
        )

    def chat(self, messages: list[dict], temperature: Optional[float] = None,
             json_mode: bool = False, max_tokens: Optional[int] = None) -> str:
        """同步补全。json_mode=True 时要求模型输出合法 JSON"""
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def stream(self, messages: list[dict],
               temperature: Optional[float] = None) -> Generator[str, None, None]:
        """流式补全，逐段 yield 文本增量"""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
            stream=True,
        )
        for event in resp:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content


def parse_json_reply(text: str) -> Optional[dict]:
    """宽容解析模型返回的 JSON（容忍 ```json 包裹与前后闲话）"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None
