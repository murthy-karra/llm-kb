from dataclasses import dataclass

from openai import OpenAI

from app.core.config import settings


# Approximate cost per 1M tokens (input/output) by model prefix
PRICING: dict[str, tuple[float, float]] = {
    # Cerebras
    "gpt-oss-120b": (0.35, 0.75),
    # Groq
    "openai/gpt-oss-120b": (0.15, 0.60),
    # OpenAI
    "gpt-5.4-mini": (0.40, 1.60),
    "gpt-5.4": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    # Google
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
}


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


def get_client(api_key: str | None = None, base_url: str | None = None) -> OpenAI:
    return OpenAI(
        api_key=api_key or settings.llm_api_key.get_secret_value(),
        base_url=base_url or settings.llm_base_url,
    )


def load_prompt(name: str, **kwargs: str) -> str:
    """Read prompts/{name}.md and format with kwargs."""
    path = settings.prompts_dir / f"{name}.md"
    template = path.read_text()
    if kwargs:
        template = template.format(**kwargs)
    return template


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICING.get(model)
    if not prices:
        # Try prefix match
        for key, val in PRICING.items():
            if model.startswith(key):
                prices = val
                break
    if not prices:
        return 0.0
    input_cost = (prompt_tokens / 1_000_000) * prices[0]
    output_cost = (completion_tokens / 1_000_000) * prices[1]
    return round(input_cost + output_cost, 6)


def ask(
    system: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMResponse:
    """Single-turn API call. Returns LLMResponse with text and usage."""
    client = get_client(api_key=api_key, base_url=base_url)
    resolved_model = model or settings.llm_model
    resolved_max = max_tokens or settings.llm_max_tokens

    # Newer OpenAI models (gpt-5+) require max_completion_tokens instead of max_tokens
    token_param = {}
    if resolved_model.startswith(("gpt-5", "gpt-4.1", "o3", "o4")):
        token_param["max_completion_tokens"] = resolved_max
    else:
        token_param["max_tokens"] = resolved_max

    response = client.chat.completions.create(
        model=resolved_model,
        **token_param,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )

    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else 0
    cost = _estimate_cost(resolved_model, prompt_tokens, completion_tokens)

    return LLMResponse(
        text=response.choices[0].message.content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        model=resolved_model,
    )


def ask_with_files(
    system: str,
    user_message: str,
    file_contents: dict[str, str],
    model: str | None = None,
    max_tokens: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMResponse:
    """Wrap each file in <document> tags, concatenate with user_message, call ask()."""
    docs = []
    for path, content in file_contents.items():
        docs.append(f'<document path="{path}">\n{content}\n</document>')
    full_message = "\n\n".join(docs) + "\n\n" + user_message
    return ask(system, full_message, model=model, max_tokens=max_tokens,
               api_key=api_key, base_url=base_url)


def ask_with_preset(
    preset_name: str,
    system: str,
    user_message: str,
    file_contents: dict[str, str] | None = None,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Call an LLM using a provider preset name (groq, openai, cerebras, etc.)."""
    from app.core.config import resolve_model_config
    config = resolve_model_config(preset_name)
    if file_contents:
        return ask_with_files(
            system, user_message, file_contents,
            model=config["model"], max_tokens=max_tokens,
            api_key=config["api_key"], base_url=config["base_url"],
        )
    return ask(
        system, user_message,
        model=config["model"], max_tokens=max_tokens,
        api_key=config["api_key"], base_url=config["base_url"],
    )
