"""AI provider abstraction for Flavor Forge.

Supports Gemini, Claude, and Ollama with a common interface.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from .config import ConfigManager

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    """Result from an AI provider call."""
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider_name: str


class AIProvider(ABC):
    """Base class for AI providers."""

    name: str
    model: str

    @abstractmethod
    async def generate(self, prompt: str) -> ProviderResult:
        """Generate text from a prompt."""
        ...

    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model!r})"


class GeminiProvider(AIProvider):
    """Google Gemini API provider."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str) -> ProviderResult:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)

        response = await model.generate_content_async(prompt)
        response_text = response.text

        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
        else:
            input_tokens = int(len(prompt.split()) * 1.3)
            output_tokens = int(len(response_text.split()) * 1.3)

        return ProviderResult(
            text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider_name=self.name,
        )


class ClaudeProvider(AIProvider):
    """Anthropic Claude API provider."""

    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.api_key = api_key
        self.model = model

    async def generate(self, prompt: str) -> ProviderResult:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self.api_key)

        response = await client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )

        return ProviderResult(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self.model,
            provider_name=self.name,
        )


class OllamaProvider(AIProvider):
    """Ollama local LLM provider."""

    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, prompt: str) -> ProviderResult:
        import urllib.request

        url = f"{self.base_url}/api/generate"
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        def _do_request():
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))

        data = await asyncio.to_thread(_do_request)

        response_text = data.get("response", "")
        # Ollama may or may not report token counts
        input_tokens = data.get("prompt_eval_count", int(len(prompt.split()) * 1.3))
        output_tokens = data.get("eval_count", int(len(response_text.split()) * 1.3))

        return ProviderResult(
            text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider_name=self.name,
        )


def get_provider(name: str, config: ConfigManager) -> AIProvider:
    """Create a provider instance by name, using config for credentials.

    Raises ValueError if the provider is not configured (missing API key/URL).
    """
    name = name.lower()

    if name == "gemini":
        api_key = config.get_api_key("gemini")
        if not api_key:
            raise ValueError("Gemini not configured: set GEMINI_API_KEY")
        model = config.get("ai_generation", "gemini_model", fallback="gemini-2.0-flash-exp")
        return GeminiProvider(api_key=api_key, model=model)

    elif name == "claude":
        api_key = config.get_api_key("anthropic")
        if not api_key:
            raise ValueError("Claude not configured: set ANTHROPIC_API_KEY")
        model = config.get("ai_generation", "claude_model", fallback="claude-sonnet-4-5-20250929")
        return ClaudeProvider(api_key=api_key, model=model)

    elif name == "ollama":
        base_url = config.get_api_key("ollama") or "http://localhost:11434"
        model = config.get("ai_generation", "ollama_model", fallback="llama3.2")
        return OllamaProvider(base_url=base_url, model=model)

    else:
        raise ValueError(f"Unknown provider: {name!r}. Available: gemini, claude, ollama")


def get_available_providers(config: ConfigManager) -> list[str]:
    """Return list of provider names that are configured and ready to use."""
    available = []

    if config.get_api_key("gemini"):
        available.append("gemini")
    if config.get_api_key("anthropic"):
        available.append("claude")

    # Ollama is always "available" since it defaults to localhost
    ollama_url = config.get_api_key("ollama") or "http://localhost:11434"
    available.append("ollama")

    return available
