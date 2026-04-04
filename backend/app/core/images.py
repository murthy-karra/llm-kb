import hashlib
import urllib.request
from pathlib import Path

from openai import OpenAI

from app.core.config import PROVIDER_PRESETS, settings


def _get_openai_client() -> OpenAI:
    key = settings.openai_api_key.get_secret_value()
    if not key:
        raise ValueError("LLMKB_OPENAI_API_KEY not set — required for image generation")
    return OpenAI(
        api_key=key,
        base_url=PROVIDER_PRESETS["openai"]["base_url"],
    )


def _image_cache_dir() -> Path:
    d = settings.assets_dir / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(article_slug: str, style: str) -> str:
    return hashlib.md5(f"{article_slug}:{style}".encode()).hexdigest()[:12]


def get_cached_image(article_slug: str, style: str = "hero") -> Path | None:
    """Return cached image path if it exists."""
    cache_dir = _image_cache_dir()
    key = _cache_key(article_slug, style)
    for ext in (".png", ".webp", ".jpg"):
        path = cache_dir / f"{key}{ext}"
        if path.exists():
            return path
    return None


def generate_article_image(
    article_slug: str,
    title: str,
    category: str,
    preview: str,
    style: str = "hero",
) -> Path:
    """Generate an image for an article using DALL-E and cache it."""
    # Check cache first
    cached = get_cached_image(article_slug, style)
    if cached:
        return cached

    client = _get_openai_client()

    if style == "hero":
        prompt = (
            f"A clean, modern editorial illustration for a knowledge base article titled "
            f'"{title}" in the category "{category}". '
            f"Context: {preview[:200]}. "
            f"Style: minimal flat vector illustration with soft gradients, muted professional "
            f"color palette (teals, warm grays, subtle accents), abstract conceptual imagery. "
            f"No text, no words, no letters. Suitable as a wide banner image for a web article."
        )
    elif style == "infographic":
        prompt = (
            f"A clean infographic-style illustration showing key concepts related to "
            f'"{title}" ({category}). '
            f"Style: modern data visualization aesthetic, clean icons and diagrams, "
            f"professional muted colors, minimal and elegant. No text or labels."
        )
    else:
        prompt = (
            f"Professional editorial illustration for: {title}. "
            f"Clean, minimal, modern vector style. No text."
        )

    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1792x1024" if style == "hero" else "1024x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url

    # Download and cache
    cache_dir = _image_cache_dir()
    key = _cache_key(article_slug, style)
    path = cache_dir / f"{key}.png"
    urllib.request.urlretrieve(image_url, str(path))

    return path
