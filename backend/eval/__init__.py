"""Retrieval evaluation harness for the evidence-to-control mapping engine.

Standalone addition, not part of the `compliance_platform` package: it
imports from and reads that package (embeddings, vector repository,
ingestion service, framework loader) but does not modify it. See
`backend/eval/README.md` for the goal, the metrics reported, and the
span-overlap relevance rule this package is built around.

Relevant prior art in `compliance_platform` that this package measures
rather than replaces: ADR-0011 (retrieval-based mapping engine, the
seam under evaluation), ADR-0005/ADR-0008 (vector store and embedding
backend choices), ADR-0033 (retrieval *speed* was benchmarked here;
retrieval *quality* was not, which is the gap this package closes).
"""
