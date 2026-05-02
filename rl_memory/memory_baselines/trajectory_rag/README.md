# Trajectory RAG

This baseline retrieves short action sketches from other task oracle traces and prepends them to the current instruction.

Design constraints:
- It is retrieval-only and does not train the model.
- It defaults to excluding the exact same task id to avoid direct oracle leakage.
- It injects short action sketches instead of full traces to limit prompt overload.
- It can use optional local embeddings via `AGENT_TRAJECTORY_RAG_EMBED_MODEL`.
