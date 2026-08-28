-- File: 001_init.sql
-- Description: Initial schema for Kaskade Memory OSS.
-- Created: 2026-08-28
-- Last updated: 2026-08-28

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY,
    memory_type TEXT NOT NULL,
    label TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}',
    tags JSONB NOT NULL DEFAULT '[]',
    embedding vector(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_core_label ON memories (label) WHERE memory_type = 'core';

CREATE TABLE IF NOT EXISTS memory_graph_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    ref_id TEXT,
    label TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS memory_graph_edges (
    id UUID PRIMARY KEY,
    src_node_id TEXT NOT NULL REFERENCES memory_graph_nodes(id),
    dst_node_id TEXT NOT NULL REFERENCES memory_graph_nodes(id),
    edge_type TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS memory_cascade_reviews (
    id UUID PRIMARY KEY,
    memory_id UUID,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_events (
    id UUID PRIMARY KEY,
    topic TEXT,
    sentiment TEXT,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS recall_gnostic_shadow_audit (
    id UUID PRIMARY KEY,
    agent_id TEXT NOT NULL,
    spark_text TEXT,
    extra JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_episode_date ON memories ((metadata->>'episode_date'));
CREATE INDEX IF NOT EXISTS idx_memories_theme_id ON memories ((metadata->>'theme_id'));
