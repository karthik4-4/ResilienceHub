"""
LangChain and LangGraph integration for LLM calls and structured outputs.
"""

from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.language_models.chat_models import BaseChatModel

from scdrc.core.config import Settings, load_settings
from scdrc.llm.fake_llm import FakeLLM

logger = logging.getLogger(__name__)


class FakeLangChainChatModel(Runnable):
    """LangChain-compatible deterministic mock chat model for offline mode."""

    def __init__(self, fake_llm: Optional[FakeLLM] = None):
        super().__init__()
        self.fake_llm = fake_llm or FakeLLM()

    def invoke(self, input: Any, config: Optional[Dict[str, Any]] = None) -> AIMessage:
        # Synchronous fallback
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.ainvoke(input, config))

    async def ainvoke(self, input: Any, config: Optional[Dict[str, Any]] = None) -> AIMessage:
        messages = []
        if isinstance(input, list):
            for m in input:
                if isinstance(m, BaseMessage):
                    messages.append({"role": "system" if isinstance(m, SystemMessage) else "user", "content": m.content})
                elif isinstance(m, dict):
                    messages.append(m)
        elif isinstance(input, str):
            messages.append({"role": "user", "content": input})

        resp = await self.fake_llm.chat_completion(messages=messages)
        return AIMessage(content=resp.get("content", "{}"))

    def with_structured_output(self, schema: Union[Type[BaseModel], Dict[str, Any]], **kwargs) -> Runnable:
        """Emulate LangChain structured output parsing."""
        async def _structured_invoke(input: Any) -> Any:
            ai_msg = await self.ainvoke(input)
            raw = ai_msg.content
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {"raw": raw}
            else:
                data = raw
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                return schema.model_validate(data)
            return data

        return RunnableLambda(_structured_invoke)


def get_langchain_chat_model(settings: Optional[Settings] = None, model: Optional[str] = None) -> Any:
    """
    Returns a configured LangChain Chat Model (ChatGroq when in live mode; FakeLangChainChatModel in offline mode).
    """
    settings = settings or load_settings()

    if settings.mode == "live" and settings.groq_api_key:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                groq_api_key=settings.groq_api_key,
                model_name=model or settings.models.reasoning,
                temperature=settings.models.temperature,
                timeout=float(settings.models.timeout_seconds),
            )
        except Exception as e:
            logger.warning(f"Failed to initialize ChatGroq: {e}. Falling back to FakeLangChainChatModel.")

    return FakeLangChainChatModel()
