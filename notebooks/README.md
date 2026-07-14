# notebooks/

Exploratory work that does not belong in production code: chunking strategy experiments, embedding model comparisons, and the hallucination-rate / mapping precision-recall evaluation notebooks referenced in `PROJECT_CHARTER.md` Section 6 (Success Metrics).

Convention: a notebook is allowed to be messy while exploring, but any finding that becomes a real decision must be written up as an ADR in `docs/adr/` and any reusable logic must graduate into `backend/src/`. Notebooks are not permitted to be the only home of decision-relevant logic — the project's audit-trail principle (see `framework_mapping/README.md`) applies here too.
