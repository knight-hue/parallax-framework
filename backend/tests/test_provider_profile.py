"""供应商差异层与请求体构造的单元测试。

重点验证"不该发的字段一定不发"：把 OpenAI 专有参数发给 DeepSeek 会直接 400，
而这类错误在长任务里很难定位。
"""

from __future__ import annotations

import pytest

from parallax.config import Settings
from parallax.infra.provider import (
    OPENAI_DEFAULT_BASE_URL,
    build_body,
    detect_provider,
    is_reasoning_model,
    resolve_profile,
)
from parallax.ports.llm import ChatMessage

MESSAGES = [ChatMessage(role="user", content="ping")]


def _settings(**overrides) -> Settings:
    base = {"llm_api_key": "test-key", "_env_file": None}
    base.update(overrides)
    return Settings(**base)


# ---- 供应商识别 ----


def test_detect_provider_by_host():
    assert detect_provider("https://api.deepseek.com") == "deepseek"
    assert detect_provider("https://api.deepseek.com/v1") == "deepseek"
    assert detect_provider(OPENAI_DEFAULT_BASE_URL) == "openai"
    assert detect_provider("https://api.openai.com/v1") == "openai"
    assert detect_provider("https://llm.internal.example/v1") == "openai_compat"


def test_explicit_provider_wins_over_host():
    assert detect_provider("https://proxy.example/v1", "deepseek") == "deepseek"
    assert detect_provider("https://api.deepseek.com", "openai_compat") == "openai_compat"
    with pytest.raises(ValueError):
        detect_provider("https://api.deepseek.com", "azure")


def test_reasoning_model_detection_differs_by_provider():
    assert is_reasoning_model("openai", "gpt-5.1") is True
    assert is_reasoning_model("openai", "gpt-4o-mini") is False
    assert is_reasoning_model("deepseek", "deepseek-reasoner") is True
    assert is_reasoning_model("deepseek", "deepseek-chat") is False
    assert is_reasoning_model("deepseek", "deepseek-v4.1-flash") is False


# ---- profile ----


def test_deepseek_defaults_are_applied_when_provider_is_explicit():
    profile = resolve_profile(_settings(llm_provider="deepseek"))
    assert profile.name == "deepseek"
    assert profile.base_url == "https://api.deepseek.com"
    assert profile.model == "deepseek-chat"
    assert profile.token_field == "max_tokens"
    assert profile.send_reasoning_effort is False


def test_deepseek_keeps_custom_base_url_and_model():
    profile = resolve_profile(
        _settings(
            llm_provider="deepseek",
            llm_base_url="https://my-proxy.example/v1",
            llm_model="deepseek-v4.1-flash",
        )
    )
    assert profile.base_url == "https://my-proxy.example/v1"
    assert profile.model == "deepseek-v4.1-flash"
    assert profile.chat_completions_url == "https://my-proxy.example/v1/chat/completions"


def test_openai_reasoning_profile_matches_previous_behaviour():
    profile = resolve_profile(_settings(llm_model="gpt-6.1-sol"))
    assert profile.name == "openai"
    assert profile.reasoning is True
    assert profile.send_temperature is False
    assert profile.token_field == "max_completion_tokens"
    assert profile.send_reasoning_effort is True


# ---- 请求体 ----


def test_deepseek_body_omits_openai_only_fields():
    profile = resolve_profile(_settings(llm_provider="deepseek", llm_model="deepseek-chat"))
    body = build_body(
        profile,
        MESSAGES,
        temperature=0.3,
        max_tokens=128,
        json_mode=True,
        use_json_mode=True,
        reasoning_effort="high",
    )
    assert body["model"] == "deepseek-chat"
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 128
    assert "max_completion_tokens" not in body
    assert "reasoning_effort" not in body
    assert body["response_format"] == {"type": "json_object"}


def test_deepseek_reasoner_omits_temperature_and_json_mode():
    profile = resolve_profile(_settings(llm_provider="deepseek", llm_model="deepseek-reasoner"))
    body = build_body(
        profile,
        MESSAGES,
        temperature=0.0,
        max_tokens=256,
        json_mode=True,
        use_json_mode=True,
        reasoning_effort=None,
    )
    assert profile.reasoning is True
    assert "temperature" not in body
    assert "response_format" not in body
    assert body["max_tokens"] == 256


def test_openai_reasoning_body_uses_completion_tokens():
    profile = resolve_profile(_settings(llm_model="gpt-6.1-sol"))
    body = build_body(
        profile,
        MESSAGES,
        temperature=0.0,
        max_tokens=64,
        json_mode=False,
        use_json_mode=True,
        reasoning_effort="low",
    )
    assert "temperature" not in body
    assert body["max_completion_tokens"] == 64
    assert body["reasoning_effort"] == "low"


def test_json_mode_respects_global_switch():
    profile = resolve_profile(_settings(llm_provider="deepseek"))
    body = build_body(
        profile,
        MESSAGES,
        temperature=0.0,
        max_tokens=None,
        json_mode=True,
        use_json_mode=False,
        reasoning_effort=None,
    )
    assert "response_format" not in body
    assert "max_tokens" not in body
