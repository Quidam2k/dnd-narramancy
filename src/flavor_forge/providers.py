"""AI provider abstraction for Flavor Forge.

Supports Gemini, Claude, Ollama, and OpenAI-compatible providers
(LM Studio, Groq, OpenRouter, Together AI).
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


class OpenAICompatibleProvider(AIProvider):
    """Generic OpenAI-compatible API provider.

    Works with any service that implements the /v1/chat/completions endpoint:
    LM Studio, Groq, OpenRouter, Together AI, etc.
    """

    def __init__(self, base_url: str, model: str, api_key: Optional[str] = None, name: str = "openai-compatible"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.name = name

    async def generate(self, prompt: str) -> ProviderResult:
        import urllib.request

        url = f"{self.base_url}/v1/chat/completions"
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 2048,
            "stream": False,
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(
            url,
            data=payload,
            headers=headers,
        )

        def _do_request():
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))

        data = await asyncio.to_thread(_do_request)

        choice = data["choices"][0]
        response_text = choice["message"]["content"]
        usage = data.get("usage", {})

        return ProviderResult(
            text=response_text,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", self.model),
            provider_name=self.name,
        )


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio local provider (no API key needed)."""

    def __init__(self, base_url: str = "http://localhost:1234", model: str = "local-model"):
        super().__init__(base_url=base_url, model=model, name="lmstudio")


class GroqProvider(OpenAICompatibleProvider):
    """Groq cloud provider (free tier available)."""

    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        super().__init__(base_url="https://api.groq.com/openai/v1", model=model, api_key=api_key, name="groq")


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter cloud provider (free models available)."""

    def __init__(self, api_key: str, model: str = "meta-llama/llama-3.1-8b-instruct:free"):
        super().__init__(base_url="https://openrouter.ai/api/v1", model=model, api_key=api_key, name="openrouter")


class TogetherProvider(OpenAICompatibleProvider):
    """Together AI cloud provider (free tier available)."""

    def __init__(self, api_key: str, model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"):
        super().__init__(base_url="https://api.together.xyz/v1", model=model, api_key=api_key, name="together")


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

    elif name == "lmstudio":
        base_url = config.get_api_key("lmstudio") or "http://localhost:1234"
        model = config.get("ai_generation", "lmstudio_model", fallback="local-model")
        return LMStudioProvider(base_url=base_url, model=model)

    elif name == "groq":
        api_key = config.get_api_key("groq")
        if not api_key:
            raise ValueError("Groq not configured: set GROQ_API_KEY")
        model = config.get("ai_generation", "groq_model", fallback="llama-3.1-8b-instant")
        return GroqProvider(api_key=api_key, model=model)

    elif name == "openrouter":
        api_key = config.get_api_key("openrouter")
        if not api_key:
            raise ValueError("OpenRouter not configured: set OPENROUTER_API_KEY")
        model = config.get("ai_generation", "openrouter_model", fallback="meta-llama/llama-3.1-8b-instruct:free")
        return OpenRouterProvider(api_key=api_key, model=model)

    elif name == "together":
        api_key = config.get_api_key("together")
        if not api_key:
            raise ValueError("Together not configured: set TOGETHER_API_KEY")
        model = config.get("ai_generation", "together_model", fallback="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo")
        return TogetherProvider(api_key=api_key, model=model)

    else:
        raise ValueError(
            f"Unknown provider: {name!r}. "
            "Available: gemini, claude, ollama, lmstudio, groq, openrouter, together"
        )


def get_available_providers(config: ConfigManager) -> list[str]:
    """Return list of provider names that are configured and ready to use."""
    available = []

    if config.get_api_key("gemini"):
        available.append("gemini")
    if config.get_api_key("anthropic"):
        available.append("claude")

    # Ollama is always "available" since it defaults to localhost
    available.append("ollama")

    if config.get_api_key("lmstudio"):
        available.append("lmstudio")
    if config.get_api_key("groq"):
        available.append("groq")
    if config.get_api_key("openrouter"):
        available.append("openrouter")
    if config.get_api_key("together"):
        available.append("together")

    return available
