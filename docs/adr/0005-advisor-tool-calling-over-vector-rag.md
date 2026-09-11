# ADR 0005: Advisor uses direct tool calling + an embedded caveat corpus, not vector-DB RAG

## Status
Accepted

## Context
The roadmap ([roadmap.md](../roadmap.md)) calls for an "AI Engineering Advisor" that answers
questions like "why did PR cycle time increase?" using both live metric data and the metric
caveats in [metrics.md](../metrics.md). The target architecture sketch (GitHub/Jira → queue →
processors → Postgres/ClickHouse → Metrics API → dashboard → LLM Advisor) implies "RAG" as the
retrieval mechanism, which is normally read as vector-embedding retrieval over a document store.

## Decision
For v0, the Advisor (`dora/advisor/`) does two simpler things instead:

1. **Live data** is fetched via Claude tool calling directly against `dora.advisor.context`
   (thin wrappers over the existing `dora.metrics` functions), not via a separate retrieval
   step — there is no "document" to retrieve, the numbers are computed on demand.
2. **Metric caveats** are embedded directly in the system prompt
   (`dora/advisor/prompts.py`), and each tool result also carries its own `caveat` field
   inline, rather than being fetched from a vector store. The entire caveat corpus is a few
   KB — smaller than what a single embedding call would cost to retrieve it.

Real (vector-DB) RAG is deferred until the caveat/knowledge corpus grows past what fits
comfortably in a system prompt — e.g. if this expands to cover team-specific runbooks,
historical incident postmortems, or a large ADR/doc corpus that no longer fits inline.

## Consequences
- Zero additional infra for v0 — no embedding model, no vector store, no ingestion pipeline
  for docs. The Advisor is a single Python process with an Anthropic API key.
- Caveats can drift from [metrics.md](../metrics.md) if one is updated without the other —
  both are maintained by hand for now. A follow-up worth doing before the corpus grows: generate
  `prompts.py`'s caveat text from `metrics.md` instead of duplicating it.
- This is explicitly a v0 choice, not a claim that vector RAG is unnecessary in general — see
  the "later" trigger above and [roadmap.md](../roadmap.md).
