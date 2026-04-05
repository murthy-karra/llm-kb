use axum::{
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, sync::Arc};
use tantivy::{
    collector::TopDocs,
    query::QueryParser,
    schema::{Field, Schema, Value, STORED, STRING, TEXT},
    Index, IndexReader, IndexWriter, TantivyDocument,
};
use tokio::sync::RwLock;
use tower_http::cors::CorsLayer;

#[derive(Parser)]
#[command(name = "llm-kb-search", about = "Wiki-scoped search engine backed by Postgres")]
struct Args {
    /// PostgreSQL connection string
    #[arg(long, env = "DATABASE_URL", default_value = "host=localhost user=llmkb password=llmkb_dev_2026 dbname=llm-kb")]
    database_url: String,

    /// Port to listen on
    #[arg(long, default_value_t = 8880)]
    port: u16,
}

struct Fields {
    wiki_id: Field,
    slug: Field,
    title: Field,
    body: Field,
    category: Field,
}

struct WikiIndex {
    index: Index,
    reader: IndexReader,
    fields: Fields,
    article_count: usize,
}

struct AppState {
    wikis: RwLock<HashMap<String, WikiIndex>>,
    db_url: String,
}

fn build_schema() -> (Schema, Fields) {
    let mut builder = Schema::builder();
    let wiki_id = builder.add_text_field("wiki_id", STRING | STORED);
    let slug = builder.add_text_field("slug", STRING | STORED);
    let title = builder.add_text_field("title", TEXT | STORED);
    let body = builder.add_text_field("body", TEXT | STORED);
    let category = builder.add_text_field("category", STRING | STORED);
    let schema = builder.build();
    (
        schema,
        Fields {
            wiki_id,
            slug,
            title,
            body,
            category,
        },
    )
}

/// Build an in-memory Tantivy index from a list of articles.
fn build_index(articles: &[Article]) -> Result<WikiIndex, Box<dyn std::error::Error>> {
    let (schema, fields) = build_schema();
    let index = Index::create_in_ram(schema);
    let mut writer: IndexWriter = index.writer(15_000_000)?;

    for article in articles {
        let mut doc = TantivyDocument::new();
        doc.add_text(fields.wiki_id, &article.wiki_id);
        doc.add_text(fields.slug, &article.slug);
        doc.add_text(fields.title, &article.title);
        doc.add_text(fields.body, &article.content);
        doc.add_text(fields.category, &article.category);
        writer.add_document(doc)?;
    }

    writer.commit()?;
    let reader = index.reader()?;

    Ok(WikiIndex {
        index,
        reader,
        fields,
        article_count: articles.len(),
    })
}

/// Load all articles for a wiki from Postgres.
async fn load_articles_from_db(
    db_url: &str,
    wiki_id: &str,
) -> Result<Vec<Article>, Box<dyn std::error::Error>> {
    let (client, connection) = tokio_postgres::connect(db_url, tokio_postgres::NoTls).await?;

    tokio::spawn(async move {
        if let Err(e) = connection.await {
            tracing::error!("Postgres connection error: {}", e);
        }
    });

    let rows = client
        .query(
            "SELECT wiki_id, slug, title, category, content FROM app.wiki_articles WHERE wiki_id = $1",
            &[&wiki_id],
        )
        .await?;

    let articles: Vec<Article> = rows
        .iter()
        .map(|row| Article {
            wiki_id: row.get(0),
            slug: row.get(1),
            title: row.get(2),
            category: row.get(3),
            content: row.get(4),
        })
        .collect();

    Ok(articles)
}

/// Load ALL articles from Postgres (for startup).
async fn load_all_articles_from_db(
    db_url: &str,
) -> Result<HashMap<String, Vec<Article>>, Box<dyn std::error::Error>> {
    let (client, connection) = tokio_postgres::connect(db_url, tokio_postgres::NoTls).await?;

    tokio::spawn(async move {
        if let Err(e) = connection.await {
            tracing::error!("Postgres connection error: {}", e);
        }
    });

    let rows = client
        .query(
            "SELECT wiki_id, slug, title, category, content FROM app.wiki_articles",
            &[],
        )
        .await?;

    let mut grouped: HashMap<String, Vec<Article>> = HashMap::new();
    for row in rows {
        let article = Article {
            wiki_id: row.get(0),
            slug: row.get(1),
            title: row.get(2),
            category: row.get(3),
            content: row.get(4),
        };
        grouped
            .entry(article.wiki_id.clone())
            .or_default()
            .push(article);
    }

    Ok(grouped)
}

// ---------- Types ----------

#[derive(Deserialize, Serialize, Clone)]
struct Article {
    wiki_id: String,
    slug: String,
    title: String,
    category: String,
    content: String,
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
    slug: String,
    title: String,
    snippet: String,
    score: f32,
    category: String,
}

#[derive(Serialize)]
struct SearchResponse {
    results: Vec<SearchResult>,
    count: usize,
    wiki_id: String,
}

#[derive(Serialize)]
struct ReindexResponse {
    wiki_id: String,
    indexed: usize,
}

#[derive(Serialize)]
struct StatsResponse {
    wikis: usize,
    total_articles: usize,
    per_wiki: HashMap<String, usize>,
}

// ---------- Handlers ----------

async fn health() -> &'static str {
    "ok"
}

async fn search_wiki(
    State(state): State<Arc<AppState>>,
    Path(wiki_id): Path<String>,
    Json(req): Json<SearchRequest>,
) -> Result<Json<SearchResponse>, StatusCode> {
    let wikis = state.wikis.read().await;
    let wiki_index = wikis.get(&wiki_id).ok_or(StatusCode::NOT_FOUND)?;

    let searcher = wiki_index.reader.searcher();
    let query_parser = QueryParser::for_index(
        &wiki_index.index,
        vec![wiki_index.fields.title, wiki_index.fields.body],
    );

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

        let slug = doc
            .get_first(wiki_index.fields.slug)
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let title = doc
            .get_first(wiki_index.fields.title)
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let body = doc
            .get_first(wiki_index.fields.body)
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let category = doc
            .get_first(wiki_index.fields.category)
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();

        let snippet: String = body.chars().take(200).collect();

        results.push(SearchResult {
            slug,
            title,
            snippet,
            score,
            category,
        });
    }

    let count = results.len();
    Ok(Json(SearchResponse {
        results,
        count,
        wiki_id,
    }))
}

async fn reindex_wiki(
    State(state): State<Arc<AppState>>,
    Path(wiki_id): Path<String>,
) -> Result<Json<ReindexResponse>, StatusCode> {
    let articles = load_articles_from_db(&state.db_url, &wiki_id)
        .await
        .map_err(|e| {
            tracing::error!("Failed to load articles for wiki {}: {}", wiki_id, e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let article_count = articles.len();
    let wiki_index = build_index(&articles).map_err(|e| {
        tracing::error!("Failed to build index for wiki {}: {}", wiki_id, e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let mut wikis = state.wikis.write().await;
    if article_count > 0 {
        wikis.insert(wiki_id.clone(), wiki_index);
    } else {
        wikis.remove(&wiki_id);
    }

    tracing::info!("Reindexed wiki {}: {} articles", wiki_id, article_count);

    Ok(Json(ReindexResponse {
        wiki_id,
        indexed: article_count,
    }))
}

async fn stats(State(state): State<Arc<AppState>>) -> Json<StatsResponse> {
    let wikis = state.wikis.read().await;
    let mut per_wiki = HashMap::new();
    let mut total = 0;
    for (id, idx) in wikis.iter() {
        per_wiki.insert(id.clone(), idx.article_count);
        total += idx.article_count;
    }
    Json(StatsResponse {
        wikis: wikis.len(),
        total_articles: total,
        per_wiki,
    })
}

// ---------- Main ----------

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let args = Args::parse();

    tracing::info!("Loading articles from Postgres...");
    let all_articles = load_all_articles_from_db(&args.database_url).await?;

    let mut wikis = HashMap::new();
    let mut total = 0;
    for (wiki_id, articles) in all_articles {
        let count = articles.len();
        total += count;
        let wiki_index = build_index(&articles)?;
        tracing::info!("  Wiki {}: {} articles indexed", wiki_id, count);
        wikis.insert(wiki_id, wiki_index);
    }
    tracing::info!("Indexed {} articles across {} wikis", total, wikis.len());

    let state = Arc::new(AppState {
        wikis: RwLock::new(wikis),
        db_url: args.database_url,
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/stats", get(stats))
        .route("/search/{wiki_id}", post(search_wiki))
        .route("/reindex/{wiki_id}", post(reindex_wiki))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = format!("0.0.0.0:{}", args.port);
    tracing::info!("Listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
