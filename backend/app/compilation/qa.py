from app.core.config import settings
from app.core.filesystem import (
    get_wiki_index_content,
    list_wiki_articles,
    read_file,
    read_with_frontmatter,
    write_output,
)
from app.core.llm import ask, ask_with_files
from app.ingestion.ingest import slugify

SYSTEM_PROMPT = """You are a research assistant with access to a personal knowledge base wiki. \
Answer the user's question thoroughly using the wiki articles provided as context.

Rules:
1. Cite articles using [[wikilinks]] when referencing specific information.
2. If the wiki does not contain enough information to fully answer, say so clearly \
and indicate what's missing.
3. Synthesize across multiple articles when relevant — don't just summarize one.
4. Be specific: include numbers, requirements, dates, and concrete details from the articles.
5. Structure longer answers with markdown headings."""


def ask_wiki(
    question: str,
    save_output: bool = True,
    output_format: str = "markdown",
) -> str:
    """Ask a question against the compiled wiki."""
    articles = list_wiki_articles()
    index_content = get_wiki_index_content()

    if len(articles) < 50:
        # Small wiki: load all articles
        file_contents = _load_all_articles(articles)
    else:
        # Large wiki: two-pass retrieval
        relevant_paths = _select_relevant_articles(index_content, question, articles)
        file_contents = _load_all_articles(relevant_paths)

    # Add index as context
    file_contents["INDEX.md"] = index_content

    answer = ask_with_files(SYSTEM_PROMPT, question, file_contents, max_tokens=8192)

    if save_output:
        slug = slugify(question)[:60]
        filename = f"qa-{slug}.md"
        output = f"# Q: {question}\n\n{answer}\n"
        write_output(filename, output)

    return answer


def _load_all_articles(articles: list) -> dict[str, str]:
    """Load articles, truncate each to ~6000 chars to fit context."""
    file_contents = {}
    for path in articles:
        rel = str(path.relative_to(settings.wiki_dir))
        content = read_file(path)
        file_contents[rel] = content[:6000]
    return file_contents


def _select_relevant_articles(
    index_content: str,
    question: str,
    all_articles: list,
) -> list:
    """Ask LLM which articles are relevant to the question."""
    system = (
        "You are a librarian. Given a wiki index and a question, return ONLY "
        "a JSON array of file paths (relative to wiki/) for articles that are "
        "relevant to answering the question. Return at most 20 paths."
    )
    user_msg = f"## Wiki Index\n{index_content}\n\n## Question\n{question}\n\nReturn the JSON array of relevant file paths."

    import json
    import re

    response = ask(system, user_msg, max_tokens=2048)

    # Parse JSON array from response
    try:
        paths = json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if match:
            paths = json.loads(match.group(0))
        else:
            # Fallback: load all
            return all_articles

    # Resolve to actual Path objects
    selected = []
    for p in paths:
        full = settings.wiki_dir / p
        if full.exists():
            selected.append(full)

    return selected if selected else all_articles
