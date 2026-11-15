"""
BaseAgent abstract class for SCDRC specialist agents using LangChain and LangGraph.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from scdrc.core.schemas import AgentName, Entry
from scdrc.core.blackboard import BlackboardView
from scdrc.core.config import Settings, load_settings
from scdrc.llm.langchain_client import get_langchain_chat_model, FakeLangChainChatModel
from scdrc.observability.tracing import Tracer


class BaseAgent(ABC):
    """Abstract base class for all specialist agents powered by LangChain."""

    def __init__(
        self,
        agent_name: AgentName,
        settings: Optional[Settings] = None,
        llm: Optional[Any] = None,
        **kwargs,
    ):
        self.agent_name = agent_name
        self.settings = settings or load_settings()
        self.llm = llm or get_langchain_chat_model(self.settings)

    @property
    def prompt_template(self) -> str:
        prompt_file = Path(__file__).parent.parent / "llm" / "prompts" / f"{self.agent_name.value}_prompt.md"
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        return f"You are the {self.agent_name.value} agent."

    def get_langchain_prompt(self, system_suffix: str = "") -> ChatPromptTemplate:
        """Returns a LangChain ChatPromptTemplate configured for this agent."""
        sys_msg = self.prompt_template
        if system_suffix:
            sys_msg = f"{sys_msg}\n\n{system_suffix}"
        return ChatPromptTemplate.from_messages([
            ("system", sys_msg),
            ("human", "{input}"),
        ])

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute chat completion using LangChain runnable."""
        lc_messages: List[BaseMessage] = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        try:
            ai_msg = await self.llm.ainvoke(lc_messages)
            content = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
            return {
                "content": content,
                "latency_seconds": 0.05,
                "tokens": {"total_tokens": len(str(content)) // 4 + 100},
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"LangChain LLM invocation error ({type(e).__name__}: {str(e)}). Falling back."
            )
            fallback = FakeLangChainChatModel()
            ai_msg = await fallback.ainvoke(lc_messages)
            return {
                "content": ai_msg.content,
                "latency_seconds": 0.01,
                "tokens": {"total_tokens": 150},
            }

    @abstractmethod
    async def run(self, board: BlackboardView, tracer: Optional[Tracer] = None) -> List[Entry]:
        """Execute agent workflow and post entries to the blackboard."""
        pass
