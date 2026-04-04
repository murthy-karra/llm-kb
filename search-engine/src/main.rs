use axum::{extract::State, http::StatusCode, routing::{get, post}, Json, Router};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::{path::PathBuf, sync::Arc};
use tantivy::{
    collector::TopDocs,
    directory::MmapDirectory,
    query::QueryParser,
    schema::{Field, Schema, Value, STORED, STRING, TEXT},
    Index, IndexReader, IndexWriter, TantivyDocument,
};
use tokio::sync::Mutex;
use tower_http::cors::CorsLayer;
use walkdir::WalkDir;

#[derive(Parser)]
#[command(name = "llm-kb-search", about = "Search engine for LLM Knowledge Base")]
struct Args {
    /// Path to the wiki directory
    #[arg(long, default_value = "../data/wiki")]
    wiki_dir: PathBuf,

    /// Port to listen on
    #[arg(long, default_value_t = 8880)]
    port: u16,
}

struct Fields {
    path: Field,
    title: Field,
    body: Field,
    category: Field,
}

struct AppState {
    index: Index,
    reader: IndexReader,
    fields: Fields,
    wiki_dir: PathBuf,
    writer: Mutex<IndexWriter>,
}

fn build_schema() -> (Schema, Fields) {
    let mut builder = Schema::builder();
    let path = builder.add_text_field("path", STRING | STORED);
    let title = builder.add_text_field("title", TEXT | STORED);
    let body = builder.add_text_field("body", TEXT | STORED);
    let category = builder.add_text_field("category", STRING | STORED);
    let schema = builder.build();
    (schema, Fields { path, title, body, category })
}

/// Extract title and category from YAML frontmatter, return remaining body.
fn extract_frontmatter(content: &str) -> (Option<String>, Option<String>, &str) {
    let trimmed = content.trim_start();
    if !trimmed.starts_with("---") {
        return (None, None, content);
    }
    if let Some(end) = trimmed[3..].find("\n---") {
        let frontmatter = &trimmed[3..3 + end];
        let body = &trimmed[3 + end + 4..];
        let mut title = None;
        let mut category = None;
        for line in frontmatter.lines() {
            let line = line.trim();
            if let Some(val) = line.strip_prefix("title:") {
                title = Some(val.trim().trim_matches('\'').trim_matches('"').to_string());
            } else if let Some(val) = line.strip_prefix("category:") {
                category = Some(val.trim().trim_matches('\'').trim_matches('"').to_string());
            }
        }
        (title, category, body)
    } else {
        (None, None, content)
    }
}

fn index_wiki(
    wiki_dir: &PathBuf,
    writer: &mut IndexWriter,
    fields: &Fields,
) -> tantivy::Result<usize> {
    writer.delete_all_documents()?;

    let mut count = 0;
    for entry in WalkDir::new(wiki_dir)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| {
            e.path().extension().map_or(false, |ext| ext == "md")
                && e.file_name() != "INDEX.md"
        })
    {
        let content = match std::fs::read_to_string(entry.path()) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let rel_path = entry
            .path()
            .strip_prefix(wiki_dir)
            .unwrap_or(entry.path())
            .to_string_lossy()
            .to_string();

        let (title, category, body) = extract_frontmatter(&content);
        let title = title.unwrap_or_else(|| {
            entry
                .path()
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string()
        });
        let category = category.unwrap_or_default();

        let mut doc = TantivyDocument::new();
        doc.add_text(fields.path, &rel_path);
        doc.add_text(fields.title, &title);
        doc.add_text(fields.body, body);
        doc.add_text(fields.category, &category);
        writer.add_document(doc)?;
        count += 1;
    }

    writer.commit()?;
    Ok(count)
}

#[derive(Deserialize)]
struct SearchRequest {
    query: String,
    #[serde(default = "default_limit")]
    limit: usize,
}

fn default_limit() -> usize {
    10
}

#[derive(Serialize)]
struct SearchResult {
    path: String,
    title: String,
    snippet: String,
    score: f32,
    category: String,
}

#[derive(Serialize)]
struct SearchResponse {
    results: Vec<SearchResult>,
    count: usize,
}

#[derive(Serialize)]
struct ReindexResponse {
    indexed: usize,
}

async fn health() -> &'static str {
    "ok"
}

async fn search(
    State(state): State<Arc<AppState>>,
    Json(req): Json<SearchRequest>,
) -> Result<Json<SearchResponse>, StatusCode> {
    let searcher = state.reader.searcher();
    let query_parser =
        QueryParser::for_index(&state.index, vec![state.fields.title, state.fields.body]);

    let query = query_parser
        .parse_query(&req.query)
        .map_err(|_| StatusCode::BAD_REQUEST)?;

    let top_docs = searcher
        .search(&query, &TopDocs::with_limit(req.limit))
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut results = Vec::new();
    for (score, doc_address) in top_docs {
        let doc: TantivyDocument = searcher
            .doc(doc_address)
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        let path = doc
            .get_first(state.fields.path)
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let title = doc
            .get_first(state.fields.title)
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let body = doc
            .get_first(state.fields.body)
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let category = doc
            .get_first(state.fields.category)
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let snippet: String = body.chars().take(200).collect();

        results.push(SearchResult {
            path,
            title,
            snippet,
            score,
            category,
        });
    }

    let count = results.len();
    Ok(Json(SearchResponse { results, count }))
}

async fn reindex(
    State(state): State<Arc<AppState>>,
) -> Result<Json<ReindexResponse>, StatusCode> {
    let mut writer = state.writer.lock().await;
    let indexed =
        index_wiki(&state.wiki_dir, &mut writer, &state.fields)
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    state.reader.reload().map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(ReindexResponse { indexed }))
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let args = Args::parse();

    let wiki_dir = std::fs::canonicalize(&args.wiki_dir).unwrap_or_else(|_| args.wiki_dir.clone());
    tracing::info!("Wiki directory: {}", wiki_dir.display());

    let (schema, fields) = build_schema();

    let index_path = wiki_dir.join(".tantivy-index");
    std::fs::create_dir_all(&index_path)?;
    let dir = MmapDirectory::open(&index_path)?;
    let index = Index::open_or_create(dir, schema)?;

    let mut writer = index.writer(50_000_000)?;
    let count = index_wiki(&wiki_dir, &mut writer, &fields)?;
    tracing::info!("Indexed {} documents", count);

    let reader = index.reader()?;

    let state = Arc::new(AppState {
        index,
        reader,
        fields,
        wiki_dir,
        writer: Mutex::new(writer),
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/search", post(search))
        .route("/reindex", post(reindex))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = format!("0.0.0.0:{}", args.port);
    tracing::info!("Listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
