# repositories/

Data access layer implementing the Repository pattern: every storage technology (relational database, vector store, filesystem) is accessed through a repository class with a stable interface, so `services/` never imports SQLite, ChromaDB, or LanceDB directly.

Why this matters for this specific project: the vector store choice (ChromaDB vs. LanceDB) is explicitly undecided until Sprint 1 (see `PROJECT_CHARTER.md` MVP scope). The repository pattern means that decision is reversible without touching business logic — a real architectural hedge, not just a textbook pattern applied for its own sake.

Planned modules (Sprint 1+): `evidence_repository.py`, `assessment_repository.py`, `vector_repository.py`.
