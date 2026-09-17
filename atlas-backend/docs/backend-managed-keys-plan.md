# Plan: Remove BYO-Key, Backend-Managed Gemini Keys Only

**Date:** 2026-07-12
**Scope:** `atlas-backend` — retiring the visitor-supplied Gemini API key path
(`X-Gemini-Api-Key`) in favor of keys configured entirely server-side.
**Status:** Draft for review — no code changes yet.

---

## 1. Why

Atlas was built as a BYO-key demo: every chat request required the visitor's
own Gemini key (`X-Gemini-Api-Key` header), used for that request only and
never stored. Now that Atlas is becoming a **full-scale product sold to
clients**, key management moves entirely to the backend — clients use the
product, they don't bring a Gemini account. This also means all usage is now
billed to keys Tarun controls, which changes the calculus on quota/cost
management (see §4) in a way BYO-key never had to worry about (cost and quota
were the visitor's problem before).

## 2. The good news: this is mostly deletion, not a rewrite

`Settings` (`app/schema/llm_settings.py`) was **already** built around a
server-side key as the base case — `self.api_key` reads
`GOOGLE_API_KEY`/`GEMINI_API_KEY` from env, `require_key()`/`require_embed_key()`
raise if unset, and both `get_gemini()`/`get_embedder()` already fall back to
a process-wide singleton when no per-call key is given. BYO-key was always the
**override** path layered on top of a working server-key default, not the
only path. Removing it means deleting the override, not building the default.

Full surface area (confirmed via `grep -rn "api_key" app/`):

| File | What's there today | What changes |
|---|---|---|
| `app/routes/chat.py:83-94` | `x_gemini_api_key` header, required, 400 if blank | Delete the header, the check, and the `api_key` local — no replacement needed |
| `app/routes/chat.py:196` | `api_key=api_key` passed into `run_agent(...)` | Delete the kwarg |
| `app/agent/agent.py:198,251,527` | `run_agent(..., api_key: str | None = None)` param, threaded to `get_gemini(api_key)` and into `execute_tool_call` | Delete the param; call `get_gemini()`/`get_embedder()` with no args everywhere |
| `app/tools/dispatch.py:29,53,68,81,112` | `api_key` param on `run_tool()`/`execute_tool_call()`, forwarded to both tools | Delete the param from both signatures and both call sites |
| `app/tools/retrieve.py:76,108-109` | `api_key` param, used for `get_gemini(api_key)` / `get_embedder(api_key)` | Delete the param; no-arg singleton calls |
| `app/tools/graph_search.py:73,104-105` | Same pattern, forwarded into `GraphIndex.load(..., gemini=, embedder=)` | Delete the param |
| `app/llm/gemini.py:24-28,179-188` | `Gemini.__init__(api_key=...)` builds a **fresh, uncached** client per BYO-key call; `get_gemini(api_key)` branches on it | Collapse to a true no-arg singleton — no per-call client construction, no branch |
| `app/llm/embedding.py:31-36,140-149` | Same pattern for embeddings | Same collapse |
| `app/schema/llm_settings.py` | Already correct — `api_key`/`embed_api_key`, `require_key()`/`require_embed_key()` | **No change.** This file was already written for the backend-key world |

Ingestion (`app/routes/documents.py`) and book listing (`app/routes/books.py`)
never took an `api_key` param in the first place — confirmed by the grep
above returning nothing for either file. Ingestion was always server-key-only;
only the chat/query path had the BYO-key override. That narrows this change
to the six files above.

## 3. Sequencing

1. **Backend first, deletion-only pass**: strip the `api_key` parameter from
   `agent.py` → `dispatch.py` → `retrieve.py`/`graph_search.py` →
   `llm/gemini.py`/`llm/embedding.py`, innermost out, so at every intermediate
   commit the code still runs (just ignoring a param that's about to
   disappear). Finish by removing the header requirement in `chat.py`.
2. **Frontend coordination (separate repo, `atlas-frontend`)**: the
   `X-Gemini-Api-Key` header and whatever UI collects/stores the visitor's key
   need to come out on that side too, and it has to ship no earlier than the
   backend stops requiring the header (or requests break) and no later than
   the backend stops reading it (or a stale UI silently sends a now-ignored
   key, masking that it's no longer BYO). Coordinate the deploy order; don't
   ship backend and frontend independently without checking.
3. **Env/secrets**: confirm `GOOGLE_API_KEY`/`GEMINI_API_KEY` (and
   `GOOGLE_API_EMBEDDING_KEY` if used) are set wherever the backend deploys —
   `require_key()` already raises a clear error if not, so this fails loudly
   rather than silently, but worth a pre-deploy checklist item.

## 4. What this unlocks: a real fallback-key/model pool

This directly changes the answer to the fallback-model question from
earlier: **yes, now build it, and it can be more than model-tier fallback.**
Under BYO-key, the backend never held more than one key at a time (the
visitor's), so failover meant "try a different model, same key." Now that the
backend owns key management outright, it can hold a **pool of its own keys**
and rotate/fail over across both keys and models:

- Quota exhaustion (429) on key A → retry on key B, same model.
- Transient overload (503) on the primary model → retry on a fallback model,
  same key (as discussed previously).
- Both combined: a small ordered list of `(key, model)` pairs tried in
  sequence, each covered by the existing tenacity retry for pure transients.

Concretely: extend `Settings` with something like `gemini_api_keys: list[str]`
(comma-separated env var, falls back to the single `api_key` for
backward-compat) and a `gemini_fallback_model: str | None`, and have
`get_gemini()`/the retry wrapper in `app/llm/gemini.py` cycle through the pool
on the specific errors `_is_overloaded_error`/quota-style errors already
detect in `chat.py` — that detection logic already exists and doesn't need to
change, just needs to trigger a key/model swap instead of only a coded
message to the client. Surface which key/model actually served the request in
the Langfuse trace (support-debuggability, same reasoning as the multi-agent
plan's `agent_id` tagging).

This is a separate, smaller follow-on piece — sequence it **after** the
BYO-key removal lands cleanly, not bundled into the same change.

## 5. Interaction with the multi-agent plan

Good news for `docs/multi-agent-architecture-plan.md`: its Phase 2 ("extract a
reusable agent core from `run_agent`") never listed `api_key` as one of the
params to parameterize, so removing it here doesn't conflict with that plan —
if anything it simplifies Phase 2's job, since a nested sub-agent call no
longer needs to thread a key through at all, just `session_id`, `tools`,
`system_prompt`, and `agent_id`.

## 6. Open questions for Tarun

1. Confirm sequencing: backend deletion pass first, frontend coordinated
   right after (§3) — any constraint on deploy ordering I should know about?
2. Single backend key today, or start the multi-key pool (§4) at the same
   time? (Recommend: ship the deletion first, standalone; the pool is a
   distinct, independently valuable change and shouldn't block this one.)
3. Does `GOOGLE_API_EMBEDDING_KEY` (separate embedding quota/billing) stay a
   second distinct key, or fold into the same pool as the generation key?
