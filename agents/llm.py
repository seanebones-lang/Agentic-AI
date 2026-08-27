"""LLM Provider abstraction for multi-provider support."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel


@dataclass
class LLMMessage:
    """Standardized message format across providers."""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class LLMResponse:
    """Standardized response format across providers."""
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None
    model: str = ""
    finish_reason: Optional[str] = None


@dataclass
class LLMUsage:
    """Token usage tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs
        self._usage = LLMUsage()

    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """Send chat completion request."""
        pass

    async def stream_chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion."""
        yield ""  # Make this a proper async generator

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        pass

    def get_usage(self) -> LLMUsage:
        """Get cumulative usage."""
        return self._usage

    def reset_usage(self) -> None:
        """Reset usage counters."""
        self._usage = LLMUsage()

    def _update_usage(self, usage: Dict[str, int]) -> None:
        """Update internal usage tracking."""
        self._usage.prompt_tokens += usage.get("prompt_tokens", 0)
        self._usage.completion_tokens += usage.get("completion_tokens", 0)
        self._usage.total_tokens += usage.get("total_tokens", 0)
        self._usage.estimated_cost_usd = self._estimate_cost(
            self._usage.prompt_tokens,
            self._usage.completion_tokens,
        )

    @abstractmethod
    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None

    @property
    def client(self):
        """Lazy client initialization."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        openai_messages = [
            {
                "role": m.role,
                "content": m.content,
                **({"tool_calls": m.tool_calls} if m.tool_calls else {}),
                **({"tool_call_id": m.tool_call_id} if m.tool_call_id else {}),
                **({"name": m.name} if m.name else {}),
            }
            for m in messages
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )

        choice = response.choices[0]
        self._update_usage(response.usage.model_dump() if response.usage else {})

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=[
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (choice.message.tool_calls or [])
            ] if choice.message.tool_calls else None,
            usage=response.usage.model_dump() if response.usage else None,
            model=response.model,
            finish_reason=choice.finish_reason,
        )

    async def stream_chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        openai_messages = [
            {
                "role": m.role,
                "content": m.content,
                **({"tool_calls": m.tool_calls} if m.tool_calls else {}),
                **({"tool_call_id": m.tool_call_id} if m.tool_call_id else {}),
                **({"name": m.name} if m.name else {}),
            }
            for m in messages
        ]

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4  # Rough approximation

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Pricing as of 2024 (per 1K tokens)
        pricing = {
            "gpt-4o": {"prompt": 0.005, "completion": 0.015},
            "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        }
        rates = pricing.get(self.model, {"prompt": 0.005, "completion": 0.015})
        return (prompt_tokens / 1000) * rates["prompt"] + (completion_tokens / 1000) * rates["completion"]


class AnthropicProvider(LLMProvider):
    """Anthropic API provider."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._client = None

    @property
    def client(self):
        """Lazy client initialization."""
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    def _convert_messages(self, messages: List[LLMMessage]) -> tuple:
        """Convert to Anthropic format (system + user/assistant)."""
        system = None
        converted = []

        for m in messages:
            if m.role == "system":
                system = m.content
            elif m.role == "tool":
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content,
                        }
                    ],
                })
            else:
                converted.append({
                    "role": m.role,
                    "content": m.content,
                })

        return system, converted

    def _convert_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict]]:
        """Convert OpenAI-style tools to Anthropic format."""
        if not tools:
            return None
        return [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {}),
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        system, converted = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        response = await self.client.messages.create(
            model=self.model,
            system=system,
            messages=converted,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=anthropic_tools,
            tool_choice={"type": tool_choice} if tool_choice else None,
            **kwargs,
        )

        # Convert usage
        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }
        self._update_usage(usage)

        # Extract content and tool calls
        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": block.input,
                    },
                })

        return LLMResponse(
            content="".join(content_parts),
            tool_calls=tool_calls if tool_calls else None,
            usage=usage,
            model=response.model,
            finish_reason=response.stop_reason,
        )

    async def stream_chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        system, converted = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        async with self.client.messages.stream(
            model=self.model,
            system=system,
            messages=converted,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=anthropic_tools,
            tool_choice={"type": tool_choice} if tool_choice else None,
            **kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def count_tokens(self, text: str) -> int:
        try:
            response = self.client.messages.count_tokens(
                model=self.model,
                messages=[{"role": "user", "content": text}],
            )
            return response.input_tokens
        except Exception:
            return len(text) // 4

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Anthropic pricing per 1K tokens (2024)
        pricing = {
            "claude-3-5-sonnet-20241022": {"prompt": 0.003, "completion": 0.015},
            "claude-3-5-haiku-20241022": {"prompt": 0.0008, "completion": 0.004},
            "claude-3-opus-20240229": {"prompt": 0.015, "completion": 0.075},
        }
        rates = pricing.get(self.model, {"prompt": 0.003, "completion": 0.015})
        return (prompt_tokens / 1000) * rates["prompt"] + (completion_tokens / 1000) * rates["completion"]


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider."""

    def __init__(
        self,
        model: str,
        api_key: str,
        azure_endpoint: str,
        api_version: str = "2024-02-15-preview",
        **kwargs,
    ):
        super().__init__(model, api_key, **kwargs)
        self.azure_endpoint = azure_endpoint
        self.api_version = api_version
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncAzureOpenAI
            self._client = AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.azure_endpoint,
                api_version=self.api_version,
            )
        return self._client

    async def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        openai_messages = [
            {
                "role": m.role,
                "content": m.content,
                **({"tool_calls": m.tool_calls} if m.tool_calls else {}),
                **({"tool_call_id": m.tool_call_id} if m.tool_call_id else {}),
                **({"name": m.name} if m.name else {}),
            }
            for m in messages
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )

        choice = response.choices[0]
        self._update_usage(response.usage.model_dump() if response.usage else {})

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=[
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (choice.message.tool_calls or [])
            ] if choice.message.tool_calls else None,
            usage=response.usage.model_dump() if response.usage else None,
            model=response.model,
            finish_reason=choice.finish_reason,
        )

    async def stream_chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        openai_messages = [
            {
                "role": m.role,
                "content": m.content,
                **({"tool_calls": m.tool_calls} if m.tool_calls else {}),
                **({"tool_call_id": m.tool_call_id} if m.tool_call_id else {}),
                **({"name": m.name} if m.name else {}),
            }
            for m in messages
        ]

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            **kwargs,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Azure pricing varies by deployment; use OpenAI as baseline
        pricing = {
            "gpt-4o": {"prompt": 0.005, "completion": 0.015},
            "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
        }
        rates = pricing.get(self.model, {"prompt": 0.005, "completion": 0.015})
        return (prompt_tokens / 1000) * rates["prompt"] + (completion_tokens / 1000) * rates["completion"]


def create_provider(
    provider: str,
    model: str,
    api_key: str,
    **kwargs,
) -> LLMProvider:
    """Factory function to create LLM provider."""
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "azure_openai": AzureOpenAIProvider,
    }

    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(providers.keys())}")

    return providers[provider](model=model, api_key=api_key, **kwargs)