-- Add the precomputed BM25 lexical-token column to the chunks table.
--
-- New ingests populate this automatically (HybridStore.add), but the column
-- must exist on the live Supabase table BEFORE the next persist run — the
-- INSERT now lists bm25_tokens, so it errors until this is applied.
--
-- Apply via the Supabase MCP `apply_migration` (tracked), per CLAUDE.md — not
-- ad-hoc psql. Existing rows get an empty array here; backfill their real
-- tokens from `text` with scripts/backfill_bm25_tokens.py (uses the exact same
-- Python tokenizer as query time, so recall stays consistent).

ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS bm25_tokens TEXT[] NOT NULL DEFAULT '{}';
