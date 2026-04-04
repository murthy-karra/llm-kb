from app.core.config import settings
from app.core.filesystem import (
    get_wiki_index_content,
    list_raw_files,
    list_wiki_articles,
    read_file,
    write_output,
)
from app.core.llm import ask_with_files

SYSTEM_PROMPT = """You are a knowledge base auditor. Your job is to review a wiki \
and produce a quality report. Analyze the wiki articles provided and report on:

1. **Contradictions** — places where two articles state conflicting facts
2. **Broken wikilinks** — [[links]] that reference articles that don't exist
3. **Coverage gaps** — raw source files that aren't represented in any wiki article
4. **Missing cross-references** — articles that discuss related topics but don't link to each other
5. **Thin articles** — articles that are too short or lack concrete details
6. **Suggested new articles** — concepts mentioned across articles that deserve their own article

For each issue, be specific: name the article, quote the problematic text, and suggest a fix.

End with a summary: overall wiki health score (1-10) and top 3 priorities."""


def lint_wiki(fix: bool = False) -> str:
    """Audit the wiki for quality issues. Returns the report."""
    index_content = get_wiki_index_content()
    articles = list_wiki_articles()
    raw_files = list_raw_files()

    # Build context
    file_contents = {"INDEX.md": index_content}

    # Load all articles (truncated for context fitting)
    for path in articles:
        rel = str(path.relative_to(settings.wiki_dir))
        content = read_file(path)
        file_contents[rel] = content[:4000]

    # Add raw file listing
    raw_listing = "\n".join(f"- {p.name}" for p in raw_files)
    file_contents["_raw_file_list.txt"] = raw_listing

    user_msg = (
        f"Review this knowledge base wiki. It has {len(articles)} articles "
        f"compiled from {len(raw_files)} raw source files.\n\n"
        f"Produce a detailed quality report."
    )

    result = ask_with_files(SYSTEM_PROMPT, user_msg, file_contents, max_tokens=8192)

    # Save report
    write_output("lint-report.md", f"# Wiki Lint Report\n\n{result.text}\n")

    return result.text
