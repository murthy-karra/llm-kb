-- Migration 004: Create wiki_jobs table
-- Date: 2026-04-04

CREATE TABLE IF NOT EXISTS app.wiki_jobs (
    id           VARCHAR(36) PRIMARY KEY,
    wiki_id      VARCHAR(36) NOT NULL REFERENCES app.wikis(id) ON DELETE CASCADE,
    job_type     VARCHAR(50) NOT NULL,
    status       VARCHAR(50) NOT NULL DEFAULT 'pending',
    result       JSONB,
    error        TEXT,
    created_by   VARCHAR(36) REFERENCES auth.users(id) ON DELETE SET NULL,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wiki_jobs_status ON app.wiki_jobs (status);
CREATE INDEX IF NOT EXISTS idx_wiki_jobs_wiki_id ON app.wiki_jobs (wiki_id);
