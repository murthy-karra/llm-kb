import json
import re

from rich import print as rprint
from rich.progress import Progress

from app.core.config import settings
from app.core.filesystem import (
    list_raw_files,
    list_wiki_articles,
    read_file,
    read_with_frontmatter,
    write_wiki_article,
)
from app.core.llm import ask, ask_with_files, load_prompt


def compile_wiki(full_rebuild: bool = False) -> list[str]:
    """Main compilation pipeline. Returns list of written article paths."""
    rprint("[bold]Starting compilation...[/bold]")

    # 1. Load full raw content
    raw_full = _load_raw_files()
    total_kb = sum(len(v) for v in raw_full.values()) / 1024
    rprint(f"  Loaded {len(raw_full)} raw sources ({total_kb:.0f} KB)")

    # 2. Gather existing wiki state (skip if full rebuild)
    wiki_state = {}
    if not full_rebuild:
        wiki_state = _gather_wiki_state()
        rprint(f"  Found {len(wiki_state)} existing wiki articles")
    else:
        rprint("  Full rebuild — ignoring existing wiki state")

    # 3. Plan articles (uses summaries for planning context)
    raw_summaries = {name: content[:4000] for name, content in raw_full.items()}
    plan = _plan_articles(raw_summaries, wiki_state)
    rprint(f"  Planned {len(plan)} articles")

    # 4. Write each article using FULL source content
    written = []
    with Progress() as progress:
        task = progress.add_task("Writing articles...", total=len(plan))
        for article in plan:
            try:
                path = _write_article(article, raw_full)
                written.append(str(path))
                progress.update(task, advance=1, description=f"Wrote {article['slug']}")
            except Exception as e:
                progress.update(task, advance=1, description=f"FAILED {article['slug']}")
                rprint(f"[red]  Error writing {article['slug']}: {e}[/red]")

    # 5. Update index
    _update_index()
    rprint(f"[green bold]Compilation complete:[/green bold] {len(written)} articles written")

    return written


def _load_raw_files() -> dict[str, str]:
    """Read all raw files in full."""
    files = {}
    for path in list_raw_files():
        files[path.name] = read_file(path)
    return files


def _gather_wiki_state() -> dict[str, str]:
    """Read existing wiki articles (first 2000 chars each)."""
    state = {}
    for path in list_wiki_articles():
        rel = str(path.relative_to(settings.wiki_dir))
        content = read_file(path)
        state[rel] = content[:2000]
    return state


def _plan_articles(raw_summaries: dict[str, str], wiki_state: dict[str, str]) -> list[dict]:
    """Send raw summaries + existing wiki state to LLM, get article plan."""
    system = load_prompt("compilation_plan_system")

    # Build the user message
    parts = ["## Raw Source Documents\n"]
    for name, content in raw_summaries.items():
        parts.append(f"### {name}\n{content}\n")

    if wiki_state:
        parts.append("\n## Existing Wiki Articles\n")
        for name, content in wiki_state.items():
            parts.append(f"### {name}\n{content}\n")
    else:
        parts.append("\n## Existing Wiki Articles\nNone — this is a fresh build.\n")

    parts.append("\nNow plan the wiki articles. Return ONLY the JSON array.")

    user_message = "\n".join(parts)
    result = ask(system, user_message, max_tokens=16384)

    return _parse_plan_json(result.text)


def _parse_plan_json(response: str) -> list[dict]:
    """Extract and parse JSON array from LLM response."""
    # Try direct parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding array brackets
    match = re.search(r"\[.*\]", response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse article plan from LLM response:\n{response[:500]}")


def _fit_sources_to_budget(
    sources: dict[str, str],
    max_chars: int = 400_000,
) -> dict[str, str]:
    """Trim sources to fit within a character budget (~100K tokens).

    Strategy: allocate budget equally across sources, then redistribute
    unused budget from short sources to long ones.
    """
    if not sources:
        return sources

    total = sum(len(v) for v in sources.values())
    if total <= max_chars:
        return sources

    # First pass: equal allocation
    per_source = max_chars // len(sources)
    fitted = {}
    surplus = 0
    long_sources = []

    for name, content in sources.items():
        if len(content) <= per_source:
            fitted[name] = content
            surplus += per_source - len(content)
        else:
            long_sources.append(name)

    # Second pass: redistribute surplus to long sources
    if long_sources:
        extra_per = surplus // len(long_sources)
        limit = per_source + extra_per
        for name in long_sources:
            fitted[name] = sources[name][:limit]

    return fitted


def _write_article(article: dict, raw_full: dict[str, str]) -> str:
    """Write a single article using relevant sources (full content, budget-fitted)."""
    system = load_prompt("compilation_write_system")

    # Gather only the relevant source files
    relevant_files = {}
    for source_name in article.get("sources", []):
        if source_name in raw_full:
            relevant_files[source_name] = raw_full[source_name]

    # Fit within context window budget (reserve ~28K tokens for system + output)
    relevant_files = _fit_sources_to_budget(relevant_files, max_chars=400_000)

    # Build the user message
    user_message = (
        f"## Article to write\n"
        f"Title: {article['title']}\n"
        f"Category: {article['category']}\n"
        f"Description: {article.get('description', '')}\n"
        f"Related articles (use [[wikilinks]] to these): {', '.join(article.get('tags', []))}\n"
        f"\nWrite this article now."
    )

    result = ask_with_files(system, user_message, relevant_files, max_tokens=8192)

    path = write_wiki_article(
        slug=article["slug"],
        title=article["title"],
        content=result.text,
        category=article["category"],
        sources=article.get("sources", []),
        tags=article.get("tags", []),
    )
    return str(path)


def _update_index():
    """Regenerate INDEX.md by scanning wiki/, grouping by category."""
    articles_by_category: dict[str, list[tuple[str, str, str]]] = {}

    for path in list_wiki_articles():
        try:
            meta, content = read_with_frontmatter(path)
        except Exception:
            continue

        title = meta.get("title", path.stem)
        category = meta.get("category", "uncategorized")
        # First non-empty line of content as summary
        summary = ""
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                summary = line[:150]
                break

        rel_path = str(path.relative_to(settings.wiki_dir))

        if category not in articles_by_category:
            articles_by_category[category] = []
        articles_by_category[category].append((title, rel_path, summary))

    # Build index content
    lines = ["# Knowledge Base Index\n"]
    for category in sorted(articles_by_category.keys()):
        lines.append(f"\n## {category.replace('-', ' ').title()}\n")
        for title, rel_path, summary in sorted(articles_by_category[category]):
            if summary:
                lines.append(f"- **[{title}]({rel_path})** — {summary}")
            else:
                lines.append(f"- **[{title}]({rel_path})**")

    total = sum(len(v) for v in articles_by_category.values())
    lines.append(f"\n---\n_{total} articles across {len(articles_by_category)} categories_\n")

    index_path = settings.wiki_dir / "INDEX.md"
    index_path.write_text("\n".join(lines) + "\n")
