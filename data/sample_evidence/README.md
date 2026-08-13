# data/sample_evidence/

Tracked (not gitignored) synthetic and public sample documents used for development and demos: publicly available C2M2 and NIST CSF 2.0 framework documentation, and fabricated example policy/evidence documents that resemble what a utility would submit, containing no real organization's data.

**Rule:** every file added here must be either (a) a public government/standards-body document, or (b) authored from scratch as a synthetic example and clearly named accordingly (e.g., `synthetic_access_control_policy_v1.pdf`). This is what makes it safe to show this repository publicly as a portfolio piece. See `PROJECT_CHARTER.md` Section 9 (Constraints).

## What's here

Two hand-authored synthetic documents are tracked in git: `synthetic_access_control_policy.md` and `synthetic_incident_response_narrative.txt`.

## Binary samples for manual testing (generated, not tracked)

Text files alone cannot exercise several ingestion paths, so the binary samples are **generated on demand** rather than committed:

```
cd backend && source .venv/bin/activate && python scripts/generate_sample_evidence.py
```

That writes five documents to `generated/` (gitignored):

| File | What it exercises |
|---|---|
| `synthetic_security_policy.pdf` | PDF text layer, page-number citations (ADR-0042), running-footer normalisation and sentence-boundary chunking (ADR-0055) |
| `synthetic_scanned_policy.pdf` | **OCR** — image-only, no text layer at all (ADR-0055). Ingests as `success_ocr` |
| `synthetic_security_policy.docx` | Structure-aware chunking via real heading styles |
| `synthetic_asset_inventory.xlsx` | Row and sheet provenance across two sheets (ADR-0041, ADR-0052) |
| `synthetic_asset_inventory.csv` | Row provenance with no sheet concept |

They are generated rather than checked in for the reason `backend/conftest.py` already gives for test fixtures: a committed binary is an opaque artifact nobody can review in a diff, and anything decision-relevant should be reproducible. All five are synthetic and carry no real organizational data, exactly as the rule above requires.
