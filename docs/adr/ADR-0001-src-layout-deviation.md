# ADR-0001: Backend uses src-layout instead of a top-level src/ directory

**Status:** Accepted
**Sprint:** 0
**Deciders:** Fraz Ahmed

## Context

The original architecture brief for this project listed `src/` and `backend/` as separate top-level directories. In a single-language repository this is unambiguous, but this repository is polyglot (Python backend, React frontend), and a top-level `src/` sibling to `backend/` and `frontend/` has no clear ownership — is React source code also "src"? Is `src/` a third, undefined language's code?

## Decision

`src/` is nested inside `backend/` as `backend/src/compliance_platform/`, following the standard Python **src layout** convention (as opposed to a flat layout with `backend/compliance_platform/` directly).

## Rationale

1. **Avoids accidental local imports.** In a flat layout, running Python from the `backend/` directory can successfully import the package even if it isn't properly installed, because the current directory is implicitly on the import path. This hides packaging bugs until the code is actually deployed or installed elsewhere — exactly the kind of bug that is invisible in a solo-developer local loop and only surfaces at the worst time (a demo, or CI). Src layout forces the package to be installed (even in editable mode) to be importable, which surfaces those bugs immediately.
2. **Matches how the package will actually be consumed.** Once `backend/` has a `pyproject.toml`, `pip install -e backend/` and a real deployment install behave identically under src layout. This is a small decision now that prevents a larger refactor later.
3. **Resolves the polyglot ambiguity** described in Context without inventing a new, unexplained top-level directory.

## Consequences

- Deviates from the literal architecture brief. This is called out explicitly (this ADR) rather than silently changed, consistent with the project's own principle that assumptions and deviations belong in a visible decision log (see `PROJECT_CHARTER.md` Section 9, Assumptions).
- Import paths inside the backend are `from compliance_platform.services import ...`, not `from backend.services import ...` — this must be documented in `backend/README.md` (done) so it isn't a surprise in Sprint 1.

## Alternatives considered

- **Top-level `src/` containing only Python code, sibling to `frontend/`:** rejected — implicitly claims "src" means "the real source code" in a repo where the frontend is equally real source code.
- **Flat layout (`backend/compliance_platform/`):** rejected for the import-safety reason above; the extra directory nesting cost is minor compared to the bug class it prevents.
