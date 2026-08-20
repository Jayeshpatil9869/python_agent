"""Tests for AI provider fallback."""

from ai.provider import GeminiProvider, OpenAIProvider, get_provider_chain
from config.settings import Settings


def test_default_provider_is_gemini():
    settings = Settings(
        ai_provider="gemini",
        gemini_api_key="test-gemini-key",
        openai_api_key="test-openai-key",
        anthropic_api_key="",
    )
    chain = get_provider_chain(settings)
    assert len(chain) == 2
    assert chain[0].name == "gemini"
    assert isinstance(chain[0], GeminiProvider)


def test_openai_preferred_with_gemini_fallback():
    settings = Settings(
        ai_provider="openai",
        openai_api_key="test-openai-key",
        gemini_api_key="test-gemini-key",
    )
    chain = get_provider_chain(settings)
    assert chain[0].name == "openai"
    assert chain[1].name == "gemini"
    assert isinstance(chain[0], OpenAIProvider)


def test_skips_providers_without_keys():
    settings = Settings(
        ai_provider="openai",
        openai_api_key="",
        gemini_api_key="test-gemini-key",
        anthropic_api_key="",
    )
    chain = get_provider_chain(settings)
    assert len(chain) == 1
    assert chain[0].name == "gemini"
