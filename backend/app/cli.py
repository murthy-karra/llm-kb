import typer
from rich import print as rprint

app = typer.Typer(name="llm-kb", help="LLM Knowledge Base CLI")

MODEL_HELP = "Provider preset (cerebras, groq, openai, openai-mini, gemini) or model name"


@app.command()
def ingest(source: str = typer.Argument(help="URL, PDF path, markdown path, or directory")):
    """Ingest a source into the knowledge base."""
    from app.core.config import ensure_dirs
    from app.ingestion.ingest import ingest as do_ingest

    ensure_dirs()
    do_ingest(source)


@app.command()
def compile(
    full: bool = typer.Option(False, "--full", help="Full rebuild instead of incremental"),
    model: str = typer.Option(None, "--model", "-m", help=MODEL_HELP),
):
    """Compile raw sources into wiki articles."""
    from app.core.config import apply_model_override, ensure_dirs, settings

    ensure_dirs()
    apply_model_override(model)
    rprint(f"[dim]Using {settings.llm_model} via {settings.llm_base_url}[/dim]")

    from app.compilation.compiler import compile_wiki

    compile_wiki(full_rebuild=full)


@app.command()
def ask(
    question: str = typer.Argument(help="Question to ask the knowledge base"),
    no_save: bool = typer.Option(False, "--no-save", help="Don't save the answer to output/"),
    model: str = typer.Option(None, "--model", "-m", help=MODEL_HELP),
):
    """Ask a question against the wiki."""
    from app.core.config import apply_model_override, ensure_dirs

    ensure_dirs()
    apply_model_override(model)

    from app.compilation.qa import ask_wiki

    answer = ask_wiki(question, save_output=not no_save)
    rprint(f"\n{answer}")


@app.command()
def lint(
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues"),
    model: str = typer.Option(None, "--model", "-m", help=MODEL_HELP),
):
    """Lint the wiki for quality issues."""
    from app.core.config import apply_model_override, ensure_dirs

    ensure_dirs()
    apply_model_override(model)

    from app.linting.linter import lint_wiki

    report = lint_wiki(fix=fix)
    rprint(f"\n{report}")


@app.command()
def status():
    """Show file counts and sizes."""
    from app.core.config import ensure_dirs, settings
    from app.core.filesystem import list_raw_files, list_wiki_articles

    ensure_dirs()

    raw_files = list_raw_files()
    wiki_articles = list_wiki_articles()

    def dir_size(path):
        return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file())

    rprint(f"[bold]Raw sources:[/bold]    {len(raw_files)} files ({dir_size(settings.raw_dir) / 1024:.1f} KB)")
    rprint(f"[bold]Wiki articles:[/bold]  {len(wiki_articles)} files ({dir_size(settings.wiki_dir) / 1024:.1f} KB)")
    rprint(f"[bold]Output files:[/bold]   {len(list(settings.output_dir.glob('*')))} files")


@app.command()
def serve():
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


def main():
    app()
