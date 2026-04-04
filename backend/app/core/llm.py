from openai import OpenAI

from app.core.config import settings


def get_client() -> OpenAI:
    return OpenAI(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
    )


def load_prompt(name: str, **kwargs: str) -> str:
    """Read prompts/{name}.md and format with kwargs."""
    path = settings.prompts_dir / f"{name}.md"
    template = path.read_text()
    if kwargs:
        template = template.format(**kwargs)
    return template


def ask(
    system: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Single-turn API call. Returns the text response."""
    client = get_client()
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
    return response.choices[0].message.content


def ask_with_files(
    system: str,
    user_message: str,
    file_contents: dict[str, str],
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Wrap each file in <document> tags, concatenate with user_message, call ask()."""
    docs = []
    for path, content in file_contents.items():
        docs.append(f'<document path="{path}">\n{content}\n</document>')
    full_message = "\n\n".join(docs) + "\n\n" + user_message
    return ask(system, full_message, model=model, max_tokens=max_tokens)
