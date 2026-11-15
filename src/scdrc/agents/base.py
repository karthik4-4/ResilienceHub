"""
BaseAgent abstract class for SCDRC specialist agents.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from scdrc.core.schemas import AgentName, Entry
from scdrc.core.blackboard import BlackboardView
from scdrc.core.config import Settings, load_settings
from scdrc.llm.groq_client import GroqClient
from scdrc.llm.fake_llm import FakeLLM
from scdrc.observability.tracing import Tracer, AgentSpan


class BaseAgent(ABC):
    """Abstract base class for all specialist agents."""

    def __init__(
        self,
        agent_name: AgentName,
        settings: Optional[Settings] = None,
        groq_client: Optional[GroqClient] = None,
        fake_llm: Optional[FakeLLM] = None,
    ):
        self.agent_name = agent_name
        self.settings = settings or load_settings()
        self.groq_client = groq_client or GroqClient(self.settings)
        self.fake_llm = fake_llm or FakeLLM()

    @property
    def prompt_template(self) -> str:
        prompt_file = Path(__file__).parent.parent / "llm" / "prompts" / f"{self.agent_name.value}_prompt.md"
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        return f"You are the {self.agent_name.value} agent."

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Call live Groq LLM if configured and in live mode; otherwise fallback to FakeLLM."""
        if self.settings.mode == "live" and self.groq_client.is_available:
            return await self.groq_client.chat_completion(
                messages=messages,
                model=model or self.settings.models.reasoning,
                temperature=temperature,
                response_format=response_format,
            )
        return await self.fake_llm.chat_completion(
            messages=messages,
            model=model or "fake-llm",
            temperature=temperature,
            response_format=response_format,
        )

    @abstractmethod
    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        """Execute agent workflow and post entries to the blackboard."""
        pass
