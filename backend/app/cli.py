import typer

app = typer.Typer(name="llm-kb", help="LLM Knowledge Base CLI")


@app.command()
def serve():
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


@app.command()
def worker():
    """Start the background worker process."""
    import asyncio
    from app.worker import main as worker_main

    asyncio.run(worker_main())


def main():
    app()
