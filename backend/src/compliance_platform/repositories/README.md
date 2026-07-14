# repositories/

Data access layer implementing the Repository pattern: every storage technology (relational database, vector store, filesystem) is accessed through a repository class with a stable interface, so `services/` never imports SQLite, ChromaDB, or LanceDB directly.

Why this matters for this specific project: the vector store choice (ChromaDB vs. LanceDB, decided in ADR-0005) and the relational store choice (SQLite vs. PostgreSQL, decided in ADR-0007) were both explicitly left open in Sprint 0. The repository pattern means those decisions are reversible without touching business logic — a real architectural hedge, not just a textbook pattern applied for its own sake.

Modules: `vector_repository.py` (Sprint 1, LanceDB), `assessment_repository.py` (Sprint 2, SQLite/SQLModel — covers both assessments and evidence links; a separate `evidence_repository.py` was not needed once `EvidenceLink` turned out to share the same session/engine and read/write patterns as `Assessment`).
