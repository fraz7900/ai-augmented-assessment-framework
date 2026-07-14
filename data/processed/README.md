# data/processed/

Parsed, chunked, and metadata-tagged output of the ingestion pipeline (Sprint 1) — the intermediate representation between raw documents and the vector store. Also holds the LanceDB vector store (`lancedb/`, Sprint 1), the SQLite assessment database (`assessments.db`, Sprint 2), and the local embedding model cache (`model_cache/`, added when the embedding backend was revisited before Sprint 3 — see ADR-0008). Gitignored at runtime; only this README is tracked. See `data/raw/README.md` for the privacy rationale, which applies identically here.

`model_cache/` holds downloaded ONNX model weights (public, not evidence — see ADR-0008 for why this one-time download does not violate the local-first evidence-privacy constraint). Safe to delete at any time; it is repopulated automatically on first use after deletion.
