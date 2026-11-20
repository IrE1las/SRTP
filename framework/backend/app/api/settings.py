"""System settings API routes (AI model configuration)."""

import os
import tempfile
from threading import RLock
from dotenv import dotenv_values, set_key
from openai import OpenAI, APIStatusError, APITimeoutError, APIConnectionError

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_roles
from app.core.config import ENV_FILE, settings
from app.models.user import User
from app.schemas.settings import AISettingsOut, AISettingsUpdate, AITestRequest

router = APIRouter()
_CONFIG_LOCK = RLock()


def _read_env() -> dict:
    """Read the .env file into a dict."""

    return {key: value for key, value in dotenv_values(ENV_FILE).items() if value is not None}


def _write_env(env: dict):
    """Persist quoted settings atomically while preserving unrelated values."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=ENV_FILE.parent,
                                         prefix='.ai-config-', delete=False) as stream:
            temporary = stream.name
            if ENV_FILE.exists():
                stream.write(ENV_FILE.read_text(encoding='utf-8'))
        for key, value in env.items():
            set_key(temporary, key, value, quote_mode='always')
        os.replace(temporary, ENV_FILE)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _mask_key(key: str) -> str:
    """Mask the middle part of an API key."""

    if len(key) <= 8:
        return key[:2] + "****" + key[-2:]
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _update_runtime_config(key: str, model: str, base_url: str):
    """Update runtime config: os.environ plus the settings instance."""

    os.environ["DEEPSEEK_API_KEY"] = key
    os.environ["DEEPSEEK_MODEL"] = model
    os.environ["DEEPSEEK_BASE_URL"] = base_url

    settings.deepseek_api_key = key
    settings.deepseek_model = model
    settings.deepseek_base_url = base_url


@router.get("/ai", response_model=AISettingsOut)
def get_ai_settings(_: User = Depends(require_roles("admin"))) -> AISettingsOut:
    """Return the current AI configuration."""

    return AISettingsOut(
        api_key_masked=_mask_key(settings.deepseek_api_key or ""),
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
    )


@router.put("/ai")
def update_ai_settings(
    data: AISettingsUpdate,
    _: User = Depends(require_roles("admin")),
) -> dict:
    """Update the AI configuration, persist it and apply it at runtime."""

    if not data.model.strip():
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    if not data.base_url.strip():
        raise HTTPException(status_code=400, detail="API 地址不能为空")

    new_model = data.model.strip()
    new_base_url = data.base_url.strip()
    with _CONFIG_LOCK:
        try:
            env = _read_env()
            new_key = (data.api_key.strip() if data.api_key and data.api_key.strip()
                       else env.get('DEEPSEEK_API_KEY', settings.deepseek_api_key or ''))
            env.update(DEEPSEEK_API_KEY=new_key, DEEPSEEK_MODEL=new_model,
                       DEEPSEEK_BASE_URL=new_base_url)
            _write_env(env)
        except OSError:
            raise HTTPException(503, 'AI配置未保存：配置存储不可写，请联系维护人员。') from None
        _update_runtime_config(new_key, new_model, new_base_url)

    return {"success": True, "message": "配置已保存并即时生效"}


@router.post("/ai/test")
def test_ai_connection(
    data: AITestRequest,
    _: User = Depends(require_roles("admin")),
) -> dict:
    """Test the AI provider connection."""

    if not settings.deepseek_api_key:
        raise HTTPException(status_code=400, detail="请先配置 API Key")

    try:
        with OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=data.base_url,
            timeout=10, max_retries=0,
        ) as client:
            response = client.chat.completions.create(
                model=data.model,
                messages=[{"role": "user", "content": "只回复四个字：连接正常"}],
                extra_body={"thinking": {"type": "disabled"}},
                max_tokens=128,
            )
        if not response.choices or response.choices[0].finish_reason != 'stop' or not (response.choices[0].message.content or '').strip():
            return {"success": False, "message": "接口已响应，但未返回完整有效的测试正文，请检查模型配置后重试。"}
        return {"success": True, "message": "连接正常"}
    except APITimeoutError:
        return {"success": False, "message": "连接测试超时，请稍后重试。"}
    except APIConnectionError:
        return {"success": False, "message": "无法连接模型接口，请检查API地址和网络。"}
    except APIStatusError as exc:
        message = '模型服务限流，请稍后重试。' if exc.status_code == 429 else '模型配置、授权或服务状态异常，请检查API Key、模型名称和API地址。'
        return {"success": False, "message": message}
    except Exception:
        return {"success": False, "message": "连接测试未完成，请检查模型配置后重试。"}
