-- Migration 005: Add per-wiki model configuration
-- Date: 2026-04-04

ALTER TABLE app.wikis ADD COLUMN IF NOT EXISTS compile_model VARCHAR(50) NOT NULL DEFAULT 'groq';
ALTER TABLE app.wikis ADD COLUMN IF NOT EXISTS polish_model VARCHAR(50) NOT NULL DEFAULT 'openai';
ALTER TABLE app.wikis ADD COLUMN IF NOT EXISTS qa_model VARCHAR(50) NOT NULL DEFAULT 'openai';
