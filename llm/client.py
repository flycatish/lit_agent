from __future__ import annotations
import json
import re
from typing import Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from config import settings

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> str:
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _JSON_OBJ_RE.search(text)
    if m:
        return m.group(0).strip()
    return text.strip()


class LLMClient:
    """直接调用 hap-gateway 的 OpenAI 兼容 API。

    绕过 opencode agent 层，完全控制 system/user prompt 和 temperature。
    用 trust_env=False 避开系统代理干扰。
    """

    def __init__(self, settings_=None):
        self.s = settings_ or settings

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.s.llm_api_key}",
            "X-Codehub-Token": self.s.llm_auth_token,
            "Content-Type": "application/json",
        }

    def _call(self, messages: list[dict], temperature: float | None = None) -> str:
        body = {
            "model": self.s.llm_model,
            "messages": messages,
            "temperature": self.s.llm_temperature if temperature is None else temperature,
            "stream": False,
        }
        with httpx.Client(verify=False, trust_env=False, timeout=self.s.llm_timeout) as c:
            r = c.post(
                f"{self.s.llm_base_url}/chat/completions",
                headers=self._headers(), json=body,
            )
            r.raise_for_status()
            if not r.text or r.text.lstrip().startswith("<"):
                raise RuntimeError(f"non-JSON response (status {r.status_code}): {r.text[:200]}")
            data = r.json()
        return data["choices"][0]["message"]["content"]

    def chat(self, system: str, user: str, temperature: float | None = None) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user})
        return self._call(msgs, temperature)

    def chat_json(self, system: str, user: str, schema: Type[T]) -> T:
        raw = self.chat(system, user)
        try:
            return schema.model_validate_json(_extract_json(raw))
        except (ValidationError, ValueError):
            retry = (f"{user}\n\n"
                     "Your previous response was not valid JSON. "
                     "Respond with ONLY a valid JSON object, no markdown fences.")
            raw = self.chat(system, retry)
            return schema.model_validate_json(_extract_json(raw))
