-- Migration 003: Create wiki_articles table
-- Date: 2026-04-04

CREATE TABLE IF NOT EXISTS app.wiki_articles (
    id          VARCHAR(36) PRIMARY KEY,
    wiki_id     VARCHAR(36) NOT NULL REFERENCES app.wikis(id) ON DELETE CASCADE,
    slug        VARCHAR(255) NOT NULL,
    title       VARCHAR(500) NOT NULL,
    category    VARCHAR(255) NOT NULL DEFAULT 'general',
    content     TEXT NOT NULL,
    sources     JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags        JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_articles_wiki_id ON app.wiki_articles (wiki_id);
CREATE INDEX IF NOT EXISTS idx_wiki_articles_wiki_category ON app.wiki_articles (wiki_id, category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wiki_articles_wiki_slug ON app.wiki_articles (wiki_id, slug);
