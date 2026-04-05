from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings


# Provider presets: --model flag shortcuts
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "cerebras": {
        "env_key": "LLMKB_CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "model": "gpt-oss-120b",
    },
    "groq": {
        "env_key": "LLMKB_GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
    },
    "openai": {
        "env_key": "LLMKB_OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.4",
    },
    "openai-mini": {
        "env_key": "LLMKB_OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.4-mini",
    },
    "gemini": {
        "env_key": "LLMKB_GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash",
    },
}


class Settings(BaseSettings):
    model_config = {"env_prefix": "LLMKB_", "env_file": ".env"}

    # LLM (default provider)
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str = "https://api.cerebras.ai/v1"
    llm_model: str = "gpt-oss-120b"
    llm_max_tokens: int = 4096

    # Provider API keys (for --model presets)
    cerebras_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")

    # AWS
    aws_profile: str = "personal"
    aws_region: str = "us-west-1"
    s3_quarantine_bucket: str = "llm-kb-wiki-quarantine"
    s3_wiki_bucket: str = "llm-kb-wiki"

    # Database
    database_url: str = "postgresql+asyncpg://llmkb:llmkb_dev_2026@localhost:5432/llm-kb"
    jwt_secret: str = "llmkb-jwt-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Search engine
    search_engine_url: str = "http://localhost:8880"

    # Prompts directory (still on filesystem — these are code, not data)
    @property
    def prompts_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "prompts"


settings = Settings()


def resolve_model_config(preset_name: str) -> dict[str, str]:
    """Return {api_key, base_url, model} for a preset name without mutating globals."""
    if preset_name not in PROVIDER_PRESETS:
        return {
            "api_key": settings.llm_api_key.get_secret_value(),
            "base_url": settings.llm_base_url,
            "model": preset_name,
        }
    preset = PROVIDER_PRESETS[preset_name]
    key_attr = preset["env_key"].removeprefix("LLMKB_").lower()
    api_key = getattr(settings, key_attr, None)
    return {
        "api_key": api_key.get_secret_value() if api_key else "",
        "base_url": preset["base_url"],
        "model": preset["model"],
    }
