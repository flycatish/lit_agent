import json
import re
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_jsonc(text: str) -> str:
    """剥掉 JSONC 的 // 和 /* */ 注释（跳过字符串内部，避免误伤 URL 里的 //）。"""
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
        elif c == '"':
            in_string = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            i = text.find("\n", i)
            if i == -1:
                break
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _load_opencode_llm() -> dict:
    """从 opencode 的配置文件读取 LLM 连接信息，任何异常返回空 dict 走兜底默认值。"""
    path = Path.home() / ".config" / "opencode" / "opencode.jsonc"
    try:
        raw = re.sub(r",\s*([}\]])", r"\1", _strip_jsonc(path.read_text(encoding="utf-8")))
        data = json.loads(raw)
        options = next(iter(data.get("provider", {}).values()), {}).get("options", {})
        model_id = str(data.get("model", "")).partition("/")[-1]
        return {
            "llm_base_url": options.get("baseURL"),
            "llm_api_key": options.get("apiKey"),
            "llm_auth_token": options.get("headers", {}).get("X-Codehub-Token"),
            "llm_model": model_id or None,
            "llm_temperature": options.get("temperature"),
        }
    except (OSError, ValueError, AttributeError):
        return {}


_OPENCODE = {k: v for k, v in _load_opencode_llm().items() if v is not None}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="LIT_", extra="ignore")

    # hap-gateway（OpenAI 兼容 API）：模型等默认读 ~/.config/opencode/opencode.jsonc，.env 可逐项覆盖
    # 内网 endpoint 和凭证（base_url / api_key / auth_token）只放 .env，代码里不放真实值
    llm_base_url: str = _OPENCODE.get("llm_base_url", "")
    llm_api_key: str = _OPENCODE.get("llm_api_key", "")
    llm_auth_token: str = _OPENCODE.get("llm_auth_token", "")
    llm_model: str = _OPENCODE.get("llm_model", "GLM5-FP8-IT")
    llm_temperature: float = _OPENCODE.get("llm_temperature", 0.1)
    llm_timeout: int = 120

    max_reflect_rounds: int = 2
    top_k_per_source: int = 5
    final_top_k: int = 10
    request_timeout: int = 20


settings = Settings()
