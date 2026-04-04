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

    # Paths
    data_dir: Path = Path("../data")

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
    s3_quarantine_bucket: str = "llm-kb-wiki-quarantine"
    s3_wiki_bucket: str = "llm-kb-wiki"

    # Database
    database_url: str = "postgresql+asyncpg://llmkb:llmkb_dev_2026@localhost:5432/llm-kb"
    jwt_secret: str = "llmkb-jwt-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Search engine
    search_engine_url: str = "http://localhost:8880"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def wiki_dir(self) -> Path:
        return self.data_dir / "wiki"

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "output"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def prompts_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "prompts"


settings = Settings()


def apply_model_override(model_flag: str | None) -> None:
    """Override LLM settings based on --model flag.

    Accepts a preset name (cerebras, groq, openai, openai-mini, gemini)
    or an explicit model name (gpt-5.4, gpt-oss-120b, etc.).
    """
    if not model_flag:
        return

    if model_flag in PROVIDER_PRESETS:
        preset = PROVIDER_PRESETS[model_flag]
        # Look up the provider-specific API key
        key_attr = preset["env_key"].removeprefix("LLMKB_").lower()
        api_key = getattr(settings, key_attr, None)
        if api_key and api_key.get_secret_value():
            settings.llm_api_key = api_key
        settings.llm_base_url = preset["base_url"]
        settings.llm_model = preset["model"]
    else:
        # Treat as explicit model name, keep current provider
        settings.llm_model = model_flag


def ensure_dirs() -> None:
    """Create all data directories and seed INDEX.md if missing."""
    for d in [settings.raw_dir, settings.wiki_dir, settings.output_dir, settings.assets_dir]:
        d.mkdir(parents=True, exist_ok=True)

    index_path = settings.wiki_dir / "INDEX.md"
    if not index_path.exists():
        index_path.write_text("# Knowledge Base Index\n\n_No articles yet._\n")
