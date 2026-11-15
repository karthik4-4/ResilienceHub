"""
Groq API Client (OpenAI-compatible) with rate limit handling, backoff, and tracing.
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx
from openai import AsyncOpenAI

from scdrc.core.config import Settings, load_settings

logger = logging.getLogger(__name__)


class GroqClient:
    """Wrapper around AsyncOpenAI configured for Groq with concurrency throttling."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or load_settings()
        self.api_key = self.settings.groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.base_url = self.settings.groq_base_url or "https://api.groq.com/openai/v1"
        self._semaphore: Optional[asyncio.Semaphore] = None

        self._client: Optional[AsyncOpenAI] = None
        if self.api_key:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=float(self.settings.models.timeout_seconds),
            )

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.settings.models.rate_limit_concurrency)
        return self._semaphore

    @property
    def is_available(self) -> bool:
        return self._client is not None and bool(self.api_key)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: int = 1500,
    ) -> Dict[str, Any]:
        """Call Groq chat completion with retries, exponential backoff, and semaphore."""
        if not self._client:
            raise RuntimeError("GroqClient is not configured with an API key.")

        target_model = model or self.settings.models.reasoning
        max_retries = self.settings.models.max_retries

        async with self._get_semaphore():
            for attempt in range(1, max_retries + 1):
                start_time = time.time()
                try:
                    kwargs: Dict[str, Any] = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if response_format:
                        kwargs["response_format"] = response_format

                    response = await self._client.chat.completions.create(**kwargs)
                    elapsed = time.time() - start_time

                    content = response.choices[0].message.content or ""
                    usage = response.usage
                    tokens = {
                        "prompt_tokens": usage.prompt_tokens if usage else 0,
                        "completion_tokens": usage.completion_tokens if usage else 0,
                        "total_tokens": usage.total_tokens if usage else 0,
                    }

                    return {
                        "content": content,
                        "latency_seconds": elapsed,
                        "tokens": tokens,
                        "model": target_model,
                    }

                except Exception as e:
                    elapsed = time.time() - start_time
                    logger.warning(
                        f"Groq API call attempt {attempt}/{max_retries} failed after {elapsed:.2f}s: {str(e)}"
                    )
                    if attempt == max_retries:
                        raise e
                    sleep_time = 2.0 ** attempt
                    await asyncio.sleep(sleep_time)

        raise RuntimeError("Unreachable: exceeded retries")
