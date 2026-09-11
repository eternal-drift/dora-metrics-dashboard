"""AI Engineering Advisor: answers natural-language questions about
engineering health by calling the same dora.metrics functions the
dashboard uses, via Claude tool calling.

See docs/roadmap.md for what this is and isn't yet (no vector-DB RAG --
metric caveats are embedded directly in the system prompt, which is small
enough that retrieval would be premature; see dora/advisor/prompts.py).
"""
