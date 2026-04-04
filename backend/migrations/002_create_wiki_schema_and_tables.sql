-- Migration 002: Create app schema and wiki tables
-- Date: 2026-04-04

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.wikis (
    id          VARCHAR(36) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_by  VARCHAR(36) NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wikis_created_by ON app.wikis (created_by);

CREATE TABLE IF NOT EXISTS app.wiki_files (
    id              VARCHAR(36) PRIMARY KEY,
    wiki_id         VARCHAR(36) NOT NULL REFERENCES app.wikis(id) ON DELETE CASCADE,
    filename        VARCHAR(255) NOT NULL,
    relative_path   VARCHAR(500) NOT NULL DEFAULT '',
    s3_key          VARCHAR(1000) NOT NULL UNIQUE,
    content_type    VARCHAR(100) NOT NULL,
    size_bytes      BIGINT NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending_scan',
    scan_started_at TIMESTAMPTZ,
    transferred_at  TIMESTAMPTZ,
    uploaded_by     VARCHAR(36) REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_files_wiki_id ON app.wiki_files (wiki_id);
CREATE INDEX IF NOT EXISTS idx_wiki_files_wiki_status ON app.wiki_files (wiki_id, status);
CREATE INDEX IF NOT EXISTS idx_wiki_files_status ON app.wiki_files (status);