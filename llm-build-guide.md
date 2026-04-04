# LLM Knowledge Base — Step-by-Step Build Guide

## Prerequisites

- uv (Python package manager — `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 20+
- Rust toolchain (rustup)
- Anthropic API key
- Git

uv handles Python version management, virtual environments, and dependency
resolution. No need to install Python separately — uv will fetch it.


---


# PART 1: PERSONAL MVP (Weeks 1–4)


## Step 1: Project Bootstrap

1. Create the repo and directory structure:

```bash
mkdir llm-kb && cd llm-kb && git init
mkdir -p frontend/src/{components,views,stores,assets}
mkdir -p search-engine/src
mkdir -p data/{raw,wiki,output,assets}
mkdir -p scripts docs
```

2. Initialize the Python backend with uv:

```bash
uv init backend --python 3.12
cd backend
mkdir -p app/{api,core,ingestion,compilation,search,linting,models}
mkdir -p prompts tools
touch app/__init__.py
touch app/{core,api,ingestion,compilation,search,linting,models}/__init__.py
```

3. Add dependencies:

```bash
# Core
uv add fastapi 'uvicorn[standard]' anthropic 'typer[all]' pydantic pydantic-settings httpx

# Document processing
uv add marker-pdf beautifulsoup4 html2text PyPDF2

# Markdown processing
uv add mistune python-frontmatter

# Utilities
uv add rich watchfiles aiofiles python-multipart

# Dev dependencies
uv add --dev pytest pytest-asyncio ruff
```

4. Add CLI entry point to `backend/pyproject.toml`:

```toml
[project.scripts]
llm-kb = "app.cli:main"
```

3. Create `backend/.env`:

```
LLMKB_ANTHROPIC_API_KEY=sk-ant-...
LLMKB_LLM_MODEL=claude-sonnet-4-20250514
LLMKB_DATA_DIR=../data
```

5. Create `backend/.env`:

```
LLMKB_ANTHROPIC_API_KEY=sk-ant-...
LLMKB_LLM_MODEL=claude-sonnet-4-20250514
LLMKB_DATA_DIR=../data
```

6. Verify:

```bash
cd backend
uv run llm-kb --help
# Should show the CLI (will fail until you write cli.py,
# but the package should install cleanly)
cd ..
```

Note: all Python commands from here on use `uv run` as the prefix.
This automatically resolves the virtualenv — no activate/deactivate needed.


## Step 2: Core Module — Config + LLM Client + Filesystem Utils

These three files are the foundation everything else imports.

### 2a. `backend/app/core/config.py`

- Use pydantic-settings `BaseSettings` with `env_prefix = "LLMKB_"`
- Define paths: data_dir, raw_dir, wiki_dir, output_dir, assets_dir, prompts_dir
- Define LLM settings: anthropic_api_key, llm_model, llm_max_tokens
- Define search_engine_url (default http://localhost:8880)
- Write an `ensure_dirs()` function that creates all directories and
  seeds `wiki/INDEX.md` if it doesn't exist

### 2b. `backend/app/core/llm.py`

- `get_client()` → returns `anthropic.Anthropic` instance
- `load_prompt(name, **kwargs)` → reads `prompts/{name}.md`, formats with kwargs
- `ask(system, user_message, model, max_tokens)` → single-turn API call, returns text
- `ask_with_files(system, user_message, file_contents: dict)` → wraps each file
  in `<document path="...">` tags, concatenates with user_message, calls `ask()`

### 2c. `backend/app/core/filesystem.py`

- `list_raw_files()` → sorted list of all .md files in raw/
- `list_wiki_articles()` → sorted list of all .md files in wiki/ (excluding INDEX.md)
- `read_file(path)` → read text
- `read_with_frontmatter(path)` → returns (metadata_dict, content) using python-frontmatter
- `write_wiki_article(slug, title, content, category, sources, tags)` → writes .md
  with frontmatter to wiki/{category}/{slug}.md. Preserves created date on updates.
- `write_output(filename, content)` → writes to output/
- `get_wiki_index_content()` → reads INDEX.md
- `build_file_manifest(directory)` → dict of {relative_path: first_500_chars}

### Test checkpoint:

```python
# In backend/:
uv run python -c "from app.core.config import settings, ensure_dirs; ensure_dirs()"
# Verify data/raw/, data/wiki/, data/wiki/INDEX.md all exist
```


## Step 3: Ingestion Pipeline

### 3a. `backend/app/ingestion/ingest.py`

Write these functions:

- `slugify(text)` → filesystem-safe slug (lowercase, no special chars, max 80 chars)
- `ingest_url(url)` → fetch with httpx, convert HTML to markdown with html2text,
  extract title from `<title>` tag, write to raw/{slug}.md with frontmatter
  (title, source URL, type: web)
- `ingest_pdf(pdf_path)` → try marker_single subprocess first, fall back to
  PyPDF2 text extraction, write to raw/{slug}.md with frontmatter
- `ingest_markdown(md_path)` → copy to raw/, inject frontmatter if missing
- `ingest_directory(dir_path)` → iterate and dispatch to appropriate handler
- `ingest(source: str)` → auto-detect: URL? PDF? Markdown? Directory? Dispatch.

### Test checkpoint:

```bash
uv run llm-kb ingest https://en.wikipedia.org/wiki/Transformer_(deep_learning_model)
uv run llm-kb ingest ./some-paper.pdf
uv run llm-kb status
# Should show: Raw sources: 2 files
```


## Step 4: CLI Entry Point

### 4a. `backend/app/cli.py`

Use Typer. Define these commands (wire them up as you build each module):

- `ingest <source>` — calls ingestion pipeline
- `compile [--full]` — calls compilation pipeline (Step 5)
- `ask "question" [--no-save]` — calls Q&A engine (Step 6)
- `lint [--fix]` — calls linter (Step 7)
- `status` — shows file counts and sizes
- `serve` — starts uvicorn

Each command should call `ensure_dirs()` first, then lazy-import the relevant
module to keep startup fast.


## Step 5: Compilation Pipeline (THE CRITICAL STEP)

This is where the product lives or dies. Spend the most time here.

### 5a. Write prompt templates

Create two files in `backend/prompts/`:

**`compilation_plan_system.md`** — System prompt for the planning phase.
Tell the LLM: you're a knowledge base compiler, given raw sources, identify
key concepts/entities/themes, plan wiki articles. Each article = one concept.
Output a JSON array of {slug, title, category, sources, tags, description}.
Iterate on this prompt until the plans are sensible.

**`compilation_write_system.md`** — System prompt for the writing phase.
Tell the LLM: write clear encyclopedic wiki articles, use [[wikilinks]] for
cross-references, include a ## Sources section, 500-2000 words, prefer prose
over bullets. Iterate on this prompt until article quality is good.

### 5b. `backend/app/compilation/compiler.py`

Implement `compile_wiki(full_rebuild: bool)` with these steps:

1. `_gather_raw_summaries()` — read all raw files, truncate each to ~4000 chars
2. `_gather_wiki_state()` — read existing wiki articles (first 2000 chars each)
   for incremental updates. Skip if full_rebuild.
3. `_plan_articles(raw_files, wiki_state)` — send raw summaries + existing
   article list to LLM with the plan prompt. Parse JSON response.
4. `_write_article(article, raw_files)` — for each planned article, send only
   the relevant source files to LLM with the write prompt. Call
   `write_wiki_article()` to save.
5. `_update_index()` — regenerate INDEX.md by scanning wiki/, grouping by
   category, extracting title from frontmatter + first line as summary.

### Test checkpoint:

```bash
# Ingest 5-10 articles on a topic you care about first
uv run llm-kb compile
uv run llm-kb status
# Should show wiki articles created
# Open data/wiki/ and read them. Are they good? Iterate on prompts.
```

### 5c. Prompt iteration loop

This is where you spend days, not hours. The cycle:

1. Compile
2. Read the output articles
3. Identify quality issues (too shallow? bad categorization? missing links?)
4. Adjust prompts
5. Rebuild: `uv run llm-kb compile --full`
6. Repeat until quality is consistently good

Common issues to watch for:
- Articles too generic (fix: tell LLM to include concrete details from sources)
- Bad categorization (fix: provide category examples in plan prompt)
- Missing cross-links (fix: tell LLM to review other planned articles)
- Duplicate concepts (fix: include existing wiki state in plan prompt)


## Step 6: Q&A Engine

### 6a. `backend/app/compilation/qa.py`

Implement `ask_wiki(question, save_output, output_format)`:

1. Read INDEX.md
2. If wiki has < 50 articles: load all articles (truncate to ~6000 chars each)
3. If wiki has 50+ articles: two-pass approach:
   a. Send INDEX.md to LLM, ask "which articles are relevant to this question?"
   b. Load only those articles
4. Send everything as context with the question to LLM
5. If save_output: write answer to output/qa-{slug}.md

System prompt: "You are a research assistant with access to a wiki. Answer
thoroughly, cite articles with [[wikilinks]], say clearly if info is insufficient."

### Test checkpoint:

```bash
uv run llm-kb ask "What are the key themes across all my sources?"
uv run llm-kb ask "Compare X and Y based on the research"
# Check data/output/ for saved answers
```


## Step 7: Linting

### 7a. `backend/app/linting/linter.py`

Implement `lint_wiki(fix: bool)`:

1. Load INDEX.md + all articles (truncated) + list of raw filenames
2. Send to LLM with audit prompt asking for:
   - Contradictions across articles
   - Broken [[wikilinks]]
   - Coverage gaps (sources not represented in wiki)
   - Missing cross-references
   - Articles that are too short or need examples
   - Suggested new articles
3. Save report to output/lint-report.md

### Test checkpoint:

```bash
uv run llm-kb lint
# Read data/output/lint-report.md — does it find real issues?
```


## Step 8: Rust Search Engine

### 8a. `search-engine/Cargo.toml`

Dependencies: tantivy, axum, tokio, serde, serde_json, tower-http (cors),
walkdir, clap, tracing.

### 8b. `search-engine/src/main.rs`

1. Define schema: path (STRING|STORED), title (TEXT|STORED),
   body (TEXT|STORED), category (STRING|STORED)
2. `index_wiki(wiki_dir)` — walk directory, read each .md file, parse
   frontmatter for title, index into Tantivy
3. `POST /search` — accept {query, limit}, use QueryParser on title+body
   fields, return ranked results with path, title, snippet, score
4. `POST /reindex` — re-run index_wiki
5. `GET /health` — return "ok"
6. CORS middleware (permissive for dev)

### 8c. Build and test:

```bash
cd search-engine && cargo build --release
./target/release/llm-kb-search --wiki-dir ../data/wiki --port 8880
# In another terminal:
curl -X POST http://localhost:8880/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "transformer", "limit": 5}'
```


## Step 9: FastAPI Backend

### 9a. `backend/app/main.py`

Set up FastAPI app with CORS middleware. Define these endpoints:

```
GET  /api/status              → {raw_count, wiki_count, sizes}
GET  /api/wiki/index          → {content: INDEX.md text}
GET  /api/wiki/articles       → {articles: [{path, title, category, tags, preview}]}
GET  /api/wiki/article/{path} → {metadata, content}
GET  /api/raw/files           → {files: [{path, size_kb}]}
GET  /api/raw/file/{path}     → {content}
POST /api/ask                 → {question, answer}
POST /api/compile             → {articles_written, paths}
POST /api/lint                → {report}
POST /api/ingest/url          → {path}
POST /api/ingest/upload       → multipart file upload
```

Each POST endpoint calls the relevant module. Long-running operations
(compile, lint) block for now; async via Celery comes in the team edition.

### Test checkpoint:

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/api/status
curl http://localhost:8000/api/wiki/articles
```


## Step 10: Vue.js Frontend

### 10a. Scaffold

```bash
cd frontend
npm create vite@latest . -- --template vue  # or manually set up
npm install vue-router pinia @vueuse/core marked highlight.js
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

Configure vite proxy: `/api` → `http://localhost:8000`

### 10b. Pinia Store (`src/stores/kb.js`)

Create a single store with:
- State: status, articles, rawFiles, loading, error
- Actions: fetchStatus, fetchArticles, fetchArticle(path), fetchRawFiles,
  askQuestion(q), compileWiki(full), lintWiki, ingestURL(url),
  searchWiki(query) (calls Tantivy at :8880)

### 10c. Views (build in this order)

1. **App.vue** — Sidebar layout with nav links (Dashboard, Wiki, Raw, Ask, Search)
2. **Dashboard.vue** — Stats cards (from /api/status), Compile/Lint buttons,
   article list
3. **WikiBrowser.vue** — Articles grouped by category, click to navigate
4. **ArticleView.vue** — Render article markdown, handle [[wikilink]] clicks
   as router navigations. Use `marked` for rendering with a custom extension
   that converts `[[link|label]]` to clickable router links.
5. **RawFiles.vue** — File list + URL ingest input
6. **AskView.vue** — Textarea for question, submit button, rendered answer
7. **SearchView.vue** — Search input, results list from Tantivy

### 10d. Markdown rendering with wikilinks

In ArticleView, before passing content to `marked`, regex-replace
`[[path|label]]` and `[[path]]` with `<a class="wikilink" data-wiki="path">label</a>`.
Add a click handler on the container that intercepts clicks on `.wikilink`
and calls `router.push(/wiki/${path})`.

### Test checkpoint:

```bash
# Terminal 1:
cd backend && uv run uvicorn app.main:app --reload
# Terminal 2:
cd search-engine && cargo run -- --wiki-dir ../data/wiki
# Terminal 3:
cd frontend && npm run dev
# Open http://localhost:5173 — you should see the dashboard
```


## Step 11: Integration Test & Polish

1. Ingest 15-20 real sources on a topic
2. Compile the wiki
3. Browse in the UI — are articles well-structured? Links working?
4. Run several Q&A queries — are answers good?
5. Run lint — does it find real issues?
6. Search — are results ranked well?
7. Fix any issues, iterate on prompts

### Add a Makefile:

```makefile
dev:
	@make -j3 backend frontend search

backend:
	cd backend && uv run uvicorn app.main:app --reload

frontend:
	cd frontend && npm run dev

search:
	cd search-engine && cargo run -- --wiki-dir ../data/wiki
```


## Step 12: Docker Compose (optional but recommended)

Create `docker-compose.yml` with services for backend, frontend (nginx),
and search-engine. Mount `data/` as a shared volume. This makes it
one-command startup: `docker compose up`.


---


# PART 2: TEAM EDITION (Weeks 5–12)


## Step 13: Add Postgres

### 13a. Set up Postgres

Add to docker-compose or use a managed instance. Add database dependencies:

```bash
cd backend
uv add asyncpg 'sqlalchemy[asyncio]'
```

### 13b. Define the data model

Create SQLAlchemy models in `backend/app/models/`:

- `Organization` — id, name, slug, settings (JSON), created_at
- `Workspace` — id, org_id, name, description, settings, created_at
- `User` — id, org_id, email, name, role (admin/editor/viewer), auth_provider_id
- `SourceConnection` — id, workspace_id, connector_type, config (encrypted JSON),
  sync_cursor, sync_schedule, status, created_by
- `SourceDocument` — id, source_connection_id, external_id, title, mime_type,
  raw_path, content_hash, permissions (JSON), last_modified_at, last_synced_at
- `WikiArticle` — id, workspace_id, slug, title, category, content_path,
  sources (JSON), tags, created_at, updated_at
- `QueryLog` — id, workspace_id, user_id, question, answer_path, created_at

### 13c. Alembic migrations

```bash
cd backend
uv add alembic
uv run alembic init alembic
# Configure alembic.ini with your database URL
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

### 13d. Scope all existing operations by workspace

Every filesystem path becomes: `data/workspaces/{workspace_id}/raw/`, etc.
Every API endpoint gets a workspace_id parameter (from auth context or URL).


## Step 14: Authentication (OIDC)

### 14a. Pick your first provider

Start with Google Workspace (simpler) or Azure AD (if targeting enterprise).

### 14b. Add auth dependencies

```bash
cd backend
uv add authlib 'python-jose[cryptography]'
```

### 14c. Implement OIDC flow

1. Register an OAuth2 application with your identity provider
2. Create `backend/app/core/auth.py`:
   - `/auth/login` → redirect to OIDC provider
   - `/auth/callback` → exchange code for tokens, create/update User record,
     set session cookie
   - `get_current_user()` dependency → validate session, return User
3. Add `Depends(get_current_user)` to all API endpoints
4. Add login page to Vue.js frontend

### 14d. Test checkpoint

Login via Google → lands on dashboard → all API calls authenticated.


## Step 15: Google Drive Connector

### 15a. `backend/app/connectors/base.py`

Define the abstract connector interface:

```python
class BaseConnector:
    async def authenticate(self, credentials) -> Session
    async def list_sources(self, folder_path) -> list[SourceItem]
    async def fetch_content(self, source_id) -> RawContent
    async def get_changes_since(self, cursor) -> tuple[list[ChangeEvent], new_cursor]
    async def resolve_permissions(self, source_id) -> list[Permission]
```

### 15b. `backend/app/connectors/google_drive.py`

1. **Auth**: Google OAuth2 (`uv add google-auth google-api-python-client`).
   User authorizes via OAuth consent screen → store refresh token (encrypted).
2. **list_sources**: `service.files().list(q="'{folder_id}' in parents")` with
   pagination. Return SourceItem for each file.
3. **fetch_content**: `service.files().get_media(fileId=...)` to download.
   Dispatch by mime type:
   - Google Docs → export as .docx → pandoc → markdown
   - Google Sheets → export as .xlsx → tabular summary
   - PDF → marker-pdf → markdown
   - Plain text/markdown → direct use
4. **get_changes_since**: `service.changes().list(pageToken=cursor)`.
   Returns list of changed file IDs + new page token.
5. **resolve_permissions**: `service.permissions().list(fileId=...)`.
   Map to internal permission structure.

### 15c. UI: Add Source Connection flow

1. New view: `SourceConnections.vue`
2. "Add Google Drive" button → OAuth consent flow → save connection
3. Folder picker: let user select which folders to sync
4. Show sync status per connection

### Test checkpoint:

```
Add Google Drive connection → select a folder → files appear in raw sources
```


## Step 16: Sync Engine

### 16a. Add Redis + Celery

```bash
cd backend
uv add 'celery[redis]' redis
```

Add Redis to docker-compose.

### 16b. `backend/app/sync/worker.py`

Define Celery tasks:

- `sync_connection(connection_id)` — fetch changes since last cursor,
  process each changed file through ingestion pipeline, update sync records
- `compile_workspace(workspace_id, full_rebuild)` — run compilation pipeline
  scoped to workspace
- `periodic_sync()` — Celery Beat task, runs every N hours, queues
  sync_connection for each active connection

### 16c. `backend/app/sync/engine.py`

Orchestration logic:

1. Call connector's `get_changes_since(last_cursor)`
2. For each change:
   - **Created/Modified**: fetch content → convert to markdown → write to
     raw/ → upsert SourceDocument record → hash content for change detection
   - **Deleted**: mark SourceDocument as deleted → flag affected wiki articles
3. Update connection's sync_cursor
4. If changes detected: queue `compile_workspace` task

### 16d. Sync dashboard

New API endpoints:
- `GET /api/sync/connections` — list connections with status
- `GET /api/sync/connections/{id}/events` — recent sync events
- `POST /api/sync/connections/{id}/trigger` — manual sync trigger

Vue view: show each connection, last sync time, file count, error count,
manual sync button.

### Test checkpoint:

```
Add a file to Google Drive → wait for sync (or trigger manually) →
file appears in raw/ → compile → appears in wiki
```


## Step 17: SharePoint Connector

### 17a. Azure AD App Registration

1. Go to Azure Portal → App registrations → New registration
2. Add API permissions: Microsoft Graph → Files.Read.All, Sites.Read.All
3. Create client secret
4. Configure redirect URI for OAuth callback

### 17b. `backend/app/connectors/sharepoint.py`

1. **Auth**: MSAL library (`uv add msal`). OAuth2 auth code flow for
   per-user access, or client credentials for app-level access.
2. **list_sources**: `GET /drives/{drive-id}/items/{item-id}/children`
   via Microsoft Graph
3. **fetch_content**: `GET /drives/{drive-id}/items/{item-id}/content`
   Dispatch by file type (same as Google Drive).
4. **get_changes_since**: `GET /drives/{drive-id}/root/delta` — Microsoft's
   delta API returns all changes since a delta token. Very efficient.
5. **Webhooks** (optional): `POST /subscriptions` to register for change
   notifications. Add a webhook receiver endpoint to FastAPI.
6. **resolve_permissions**: `GET /drives/{drive-id}/items/{item-id}/permissions`

### Test checkpoint:

Same as Google Drive — add connection, select site/library, files sync.


## Step 18: Access Control

### 18a. Permission model

Add to `backend/app/core/permissions.py`:

- `can_user_view_article(user, article)` → check: does user have read access
  to ALL source documents cited by this article?
- `get_visible_articles(user, workspace)` → filter article list
- `get_permitted_context(user, articles)` → for Q&A, only include articles
  the user can see

### 18b. Permission mapping

When syncing, store source permissions in SourceDocument.permissions as JSON:

```json
{
  "type": "google_drive",
  "users": ["user@company.com"],
  "groups": ["engineering@company.com"],
  "anyone_with_link": false
}
```

At query time, resolve user's identity (email, group memberships from OIDC
claims) against these stored permissions.

### 18c. Apply filtering everywhere

- Wiki browser: filter by `get_visible_articles()`
- Q&A engine: only include permitted articles in LLM context
- Search: post-filter Tantivy results by permission
- API: all article endpoints check permissions

### 18d. Test checkpoint:

```
User A has access to SharePoint folder X but not Y.
Articles derived from Y should NOT appear for User A.
Q&A should not reference content from Y when User A asks questions.
```


## Step 19: Admin Panel

### 19a. API endpoints

- `GET/POST /api/admin/users` — list, invite, update roles
- `GET/POST /api/admin/workspaces` — create, configure
- `GET /api/admin/activity` — query log, sync events

### 19b. Vue views

- `AdminUsers.vue` — user list, role management, invite flow
- `AdminWorkspaces.vue` — workspace creation and settings
- `AdminActivity.vue` — activity feed (who queried what, sync history)


## Step 20: Production Hardening

### 20a. Docker Compose (production)

Backend Dockerfile should use the official uv Docker image as base:

```dockerfile
# backend/Dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    depends_on: [postgres, redis]
  frontend:
    build: ./frontend  # nginx serving built Vue app
    ports: ["80:80"]
  search:
    build: ./search-engine
    volumes: ["data:/data"]
  celery:
    build: ./backend
    command: uv run celery -A app.sync.worker worker
  celery-beat:
    build: ./backend
    command: uv run celery -A app.sync.worker beat
  postgres:
    image: postgres:16
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7-alpine
  
volumes:
  data:
  pgdata:
```

### 20b. Remaining checklist

- [ ] Encrypted credential storage (Fernet for connector tokens)
- [ ] Rate limiting on API endpoints
- [ ] Error handling + retry logic in sync workers
- [ ] Health check endpoints for all services
- [ ] Logging (structured JSON → stdout for container collection)
- [ ] Backup strategy for Postgres + data volume
- [ ] HTTPS (Caddy or nginx with Let's Encrypt)
- [ ] Environment-specific configs (dev/staging/prod)


---


# Summary: What to Build When

| Week | Milestone                                          |
|------|----------------------------------------------------|
| 1    | Steps 1–4: Bootstrap, core modules, ingestion, CLI |
| 2    | Steps 5–6: Compilation pipeline, Q&A (MOST TIME HERE) |
| 3    | Steps 7–9: Linting, search engine, FastAPI backend |
| 4    | Steps 10–12: Vue.js frontend, integration, Docker  |
| 5–6  | Steps 13–14: Postgres, auth (OIDC)                 |
| 7–8  | Steps 15–16: Google Drive connector, sync engine    |
| 9–10 | Steps 17–18: SharePoint connector, access control   |
| 11–12| Steps 19–20: Admin panel, production hardening      |