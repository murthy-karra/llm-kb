from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from app.core.config import settings


def list_raw_files() -> list[Path]:
    """Sorted list of all .md files in raw/."""
    return sorted(settings.raw_dir.glob("**/*.md"))


def list_wiki_articles() -> list[Path]:
    """Sorted list of all .md files in wiki/, excluding INDEX.md."""
    return sorted(p for p in settings.wiki_dir.glob("**/*.md") if p.name != "INDEX.md")


def read_file(path: Path) -> str:
    return path.read_text()


def read_with_frontmatter(path: Path) -> tuple[dict, str]:
    """Returns (metadata_dict, content) using python-frontmatter."""
    post = frontmatter.load(str(path))
    return dict(post.metadata), post.content


def write_wiki_article(
    slug: str,
    title: str,
    content: str,
    category: str,
    sources: list[str],
    tags: list[str],
) -> Path:
    """Write .md with frontmatter to wiki/{category}/{slug}.md. Preserves created date on updates."""
    cat_dir = settings.wiki_dir / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    path = cat_dir / f"{slug}.md"

    now = datetime.now(timezone.utc).isoformat()
    created = now

    # Preserve created date if article already exists
    if path.exists():
        existing_meta, _ = read_with_frontmatter(path)
        if "created" in existing_meta:
            created = existing_meta["created"]

    metadata = {
        "title": title,
        "category": category,
        "sources": sources,
        "tags": tags,
        "created": created,
        "updated": now,
    }

    post = frontmatter.Post(content, **metadata)
    path.write_text(frontmatter.dumps(post) + "\n")
    return path


def write_output(filename: str, content: str) -> Path:
    path = settings.output_dir / filename
    path.write_text(content)
    return path


def get_wiki_index_content() -> str:
    return read_file(settings.wiki_dir / "INDEX.md")


def build_file_manifest(directory: Path) -> dict[str, str]:
    """Dict of {relative_path: first_500_chars} for all .md files."""
    manifest = {}
    for path in sorted(directory.glob("**/*.md")):
        rel = str(path.relative_to(directory))
        manifest[rel] = path.read_text()[:500]
    return manifest
