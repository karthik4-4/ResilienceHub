"""
Configuration manager for SCDRC.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv
import yaml
from pydantic import BaseModel, Field

# Load .env file automatically
load_dotenv()


class ModelConfig(BaseModel):
    reasoning: str = "llama-3.3-70b-versatile"
    fast: str = "llama-3.1-8b-instant"
    temperature: float = 0.1
    max_retries: int = 3
    timeout_seconds: int = 30
    rate_limit_concurrency: int = 2


class TimeoutConfig(BaseModel):
    agent_timeout_seconds: int = 20
    case_timeout_seconds: int = 60


class ThresholdConfig(BaseModel):
    stockout_risk_days: int = 7
    critical_cover_days: int = 3
    finance_approval_amount_inr: float = 1500000.0
    minimum_confidence: float = 0.70


class WeightConfig(BaseModel):
    cost_weight: float = 0.50
    lead_time_weight: float = 0.30
    reliability_weight: float = 0.20


class CostRateConfig(BaseModel):
    default_holding_cost_rate_annual: float = 0.18
    default_stockout_penalty_per_unit_day: float = 250.0
    expedite_base_fee_inr: float = 25000.0


class PathConfig(BaseModel):
    database_url: str = "sqlite:///./data/scdrc.db"
    chroma_persist_dir: str = "./data/chroma_db"
    outputs_dir: str = "./outputs"
    scenarios_dir: str = "./data/scenarios"
    seed_dir: str = "./data/seed"


class Settings(BaseModel):
    name: str = "SCDRC"
    version: str = "0.1.0"
    mode: str = "offline"  # 'live' or 'offline'
    groq_api_key: Optional[str] = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    models: ModelConfig = Field(default_factory=ModelConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)
    weights: WeightConfig = Field(default_factory=WeightConfig)
    cost_rates: CostRateConfig = Field(default_factory=CostRateConfig)
    paths: PathConfig = Field(default_factory=PathConfig)


def load_settings(config_path: Optional[str] = None) -> Settings:
    """Load settings from YAML file with environment variable overrides."""
    if not config_path:
        default_yaml = Path(__file__).parent.parent.parent.parent / "configs" / "settings.yaml"
        if default_yaml.exists():
            config_path = str(default_yaml)

    data: Dict[str, Any] = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    app_data = data.get("app", {})
    models_data = data.get("models", {})
    timeouts_data = data.get("timeouts", {})
    thresholds_data = data.get("thresholds", {})
    weights_data = data.get("weights", {})
    cost_rates_data = data.get("cost_rates", {})
    paths_data = data.get("paths", {})

    # Environment variables
    mode = os.getenv("SCDRC_MODE", "offline")
    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_base = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    groq_reasoning = os.getenv("GROQ_MODEL_REASONING", models_data.get("reasoning", "llama-3.3-70b-versatile"))
    groq_fast = os.getenv("GROQ_MODEL_FAST", models_data.get("fast", "llama-3.1-8b-instant"))

    models_data["reasoning"] = groq_reasoning
    models_data["fast"] = groq_fast

    settings = Settings(
        name=app_data.get("name", "SCDRC"),
        version=app_data.get("version", "0.1.0"),
        mode=mode,
        groq_api_key=groq_key if groq_key else None,
        groq_base_url=groq_base,
        models=ModelConfig(**models_data),
        timeouts=TimeoutConfig(**timeouts_data),
        thresholds=ThresholdConfig(**thresholds_data),
        weights=WeightConfig(**weights_data),
        cost_rates=CostRateConfig(**cost_rates_data),
        paths=PathConfig(**paths_data),
    )
    return settings
