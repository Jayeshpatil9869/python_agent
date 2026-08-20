"""AI provider abstraction with automatic fallback."""

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

from config.settings import Settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class ProviderError(Exception):
    """Raised when an AI provider request fails."""


class AIProvider(ABC):
    name: str = "unknown"

    @abstractmethod
    async def analyze(self, system_prompt: str, user_prompt: str) -> str:
        ...


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model

    async def analyze(self, system_prompt: str, user_prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

        content = response.choices[0].message.content or ""
        if not content.strip():
            raise ProviderError("Empty response from OpenAI")
        return content


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022") -> None:
        self.api_key = api_key
        self.model = model

    async def analyze(self, system_prompt: str, user_prompt: str) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

        if not response.content:
            raise ProviderError("Empty response from Anthropic")
        return response.content[0].text


class GeminiProvider(AIProvider):
    name = "gemini"

    MODELS = (
        "gemini-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-flash-latest",
    )

    def __init__(self, api_key: str, model: str | None = None) -> None:
        self.api_key = api_key
        self.model = model

    async def analyze(self, system_prompt: str, user_prompt: str) -> str:
        models_to_try = [self.model] if self.model else list(self.MODELS)
        errors: list[str] = []

        for model_name in models_to_try:
            if not model_name:
                continue
            try:
                text = await self._generate(model_name, system_prompt, user_prompt)
                if text.strip():
                    return text
                errors.append(f"{model_name}: empty response")
            except ProviderError as exc:
                errors.append(str(exc))
            except Exception as exc:
                errors.append(f"{model_name}: {exc}")

        raise ProviderError("Gemini failed for all models: " + "; ".join(errors))

    async def _generate(self, model: str, system_prompt: str, user_prompt: str) -> str:
        url = f"{GEMINI_API_BASE}/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.3},
        }

        last_error = ""
        for attempt in range(3):
            async with httpx.AsyncClient(timeout=120.0) as client:
                try:
                    response = await client.post(
                        url,
                        headers={
                            "Content-Type": "application/json",
                            "X-goog-api-key": self.api_key,
                        },
                        json=payload,
                    )
                except httpx.HTTPError as exc:
                    raise ProviderError(str(exc)) from exc

            if response.status_code == 200:
                break

            last_error = f"{model}: HTTP {response.status_code} - {response.text[:500]}"
            if response.status_code == 503 and attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            raise ProviderError(last_error)
        else:
            raise ProviderError(last_error)

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderError(f"{model}: no candidates in response")

        parts = candidates[0].get("content", {}).get("parts") or []
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        return "\n".join(text_parts)


class LocalProvider(AIProvider):
    name = "local"

    async def analyze(self, system_prompt: str, user_prompt: str) -> str:
        raise ProviderError("Local AI provider not configured")


def _build_provider(name: str, settings: Settings) -> AIProvider | None:
    if name == "openai" and settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key)
    if name == "anthropic" and settings.anthropic_api_key:
        return AnthropicProvider(settings.anthropic_api_key)
    if name == "gemini" and settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key, model=settings.gemini_model or None)
    if name == "local":
        return LocalProvider()
    return None


def get_provider(settings: Settings) -> AIProvider | None:
    """Return the configured primary provider, if available."""
    if settings.ai_provider == "none":
        return None
    return _build_provider(settings.ai_provider, settings)


def get_provider_chain(settings: Settings) -> list[AIProvider]:
    """Build ordered provider chain: preferred first, then fallbacks."""
    preferred = settings.ai_provider
    fallback_order = ["gemini", "openai", "anthropic"]

    ordered_names: list[str] = []
    if preferred not in ("none", "local"):
        ordered_names.append(preferred)
    for name in fallback_order:
        if name not in ordered_names:
            ordered_names.append(name)

    providers: list[AIProvider] = []
    for name in ordered_names:
        provider = _build_provider(name, settings)
        if provider:
            providers.append(provider)
    return providers


async def analyze_with_fallback(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, str]:
    """
    Try providers in order until one succeeds.

    Returns:
        (analysis_text, provider_name_used)
    """
    providers = get_provider_chain(settings)
    if not providers:
        raise ProviderError(
            "No AI providers configured. Set AI_PROVIDER and at least one API key in .env"
        )

    errors: list[str] = []
    for provider in providers:
        try:
            logger.info("Trying AI provider: %s", provider.name)
            result = await provider.analyze(system_prompt, user_prompt)
            logger.info("AI analysis succeeded with provider: %s", provider.name)
            return result, provider.name
        except ProviderError as exc:
            message = f"{provider.name}: {exc}"
            logger.warning("AI provider failed: %s", message)
            errors.append(message)
        except Exception as exc:
            message = f"{provider.name}: {exc}"
            logger.warning("AI provider unexpected error: %s", message)
            errors.append(message)

    raise ProviderError("All AI providers failed:\n" + "\n".join(errors))
