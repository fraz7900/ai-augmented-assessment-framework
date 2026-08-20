# backend/eval/corpus/ — Evaluation Corpus

Documents the retrieval-eval labels (`backend/eval/labels/`) are written against. Every file here
is genuinely public, per `.cursor/rules/privacy-protection.mdc` and `data/sample_evidence/README.md`'s
existing rule ("public government/standards-body document, or a synthetic example"). No confidential
or organization-specific material appears anywhere in this directory.

## What's here

Three newly added public-domain U.S. federal government documents, each with a `SOURCE:` line
(the canonical DOI or agency download URL) as the first line of the file, plus a short provenance
header (title, author, publisher, date, and the public-domain basis):

| File | Source | Why it's public domain |
|---|---|---|
| `nistir_7621r1_small_business_fundamentals.txt` | [NISTIR 7621 Rev. 1](https://doi.org/10.6028/NIST.IR.7621r1), NIST, Nov 2016 | U.S. federal government work (17 U.S.C. §105) |
| `doe_cybersecurity_procurement_language_energy_delivery_2014.txt` | [DOE Cybersecurity Procurement Language for Energy Delivery Systems](https://www.energy.gov/oe/downloads/cybersecurity-procurement-language-energy-delivery-april-2014), DOE, Apr 2014 | U.S. federal government work (17 U.S.C. §105) |
| `nist_sp1300_csf20_small_business_quickstart.txt` | [NIST SP 1300](https://doi.org/10.6028/NIST.SP.1300), NIST, Feb 2024 | U.S. federal government work (17 U.S.C. §105) |

Text was extracted verbatim from each agency's own official PDF with `pypdf` (already a backend
dependency — see `backend/pyproject.toml`, no new dependency added for this), page by page, with
`----- page N -----` markers matching the source PDF's own page numbers. Extraction artifacts (an
occasional mid-word line break from the PDF's layout, e.g. "Cel\nia Paulsen") were left as-is rather
than hand-corrected — that's what this platform's own `document_parsers.py` produces from a real
PDF too, and a labels corpus that reads more cleanly than real evidence would defeat part of the
point of evaluating retrieval against realistic input.

**Why federal-government sources specifically:** every other genuinely public candidate this stage
tried either couldn't be fetched at all (CISA's site returned HTTP 403 to automated fetching, so no
CISA fact sheet could be verified or retrieved) or is *publicly viewable* without being *confirmed
freely redistributable* — a real university's or utility's posted security policy is typically still
under that organization's copyright regardless of being reachable at a public URL, and this stage's
own ground rule is "do not download anything you cannot confirm is public." A U.S. federal agency's
own publication is the one category where "publicly posted" and "public domain" are the same fact
(17 U.S.C. §105), so this round stopped at three of those rather than guess on the rest.

**Kept in scope, not duplicated here:** the two pre-existing synthetic documents in
`data/sample_evidence/` (`synthetic_access_control_policy.md`,
`synthetic_incident_response_narrative.txt`) remain part of the eval corpus — see
`backend/eval/labels/labels.template.yaml`, whose two EXAMPLE rows already reference them by their
existing repo path. They are not copied into this directory, to avoid a second copy drifting from
the original.

## Topical coverage (for planning labels)

- `nistir_7621r1_small_business_fundamentals.txt` — broad: asset management, access control,
  workforce training, data protection, incident response, backups. Good general-purpose coverage
  across many C2M2 domains and NIST CSF functions, but broad rather than deep on any one.
- `doe_cybersecurity_procurement_language_energy_delivery_2014.txt` — OT/ICS-specific contract
  language: authentication and session management, physical/perimeter access, wireless, cryptographic
  system management, patch management, logging, incident reporting. The best topical match to this
  platform's actual domain (energy-sector OT), and the richest source for `c2m2_v2_1`'s `ACCESS-*`
  and `ARCHITECTURE-*` practices specifically.
- `nist_sp1300_csf20_small_business_quickstart.txt` — organized directly by the six NIST CSF 2.0
  Functions (Govern, Identify, Protect, Detect, Respond, Recover), so it maps unusually cleanly to
  `framework: nist_csf_2_0` labels in particular.
- The two synthetic documents in `data/sample_evidence/` — narrower and more concrete (a specific
  fictional utility's actual policy language), good for a handful of high-confidence labels each.

## What I still need from you

1. **A decision on whether three new documents is enough for this stage**, or whether you want a
   fourth/fifth — if so, a document *you* can personally vouch is public or permissively licensed
   (a university's or utility's own confirmation that their posted policy may be redistributed would
   satisfy this; I couldn't verify that from the outside for any candidate I found).
2. **The actual relevance labels** — per `RETRIEVAL_EVAL_WORKPLAN.md` Stage 1 and
   `backend/eval/CLAUDE.md` rule 4, I do not write these; `backend/eval/labels/labels.template.yaml`
   has the schema and two clearly-marked EXAMPLE rows to copy the format from. Suggested rough
   allocation toward the 40–60+ label target, weighted by each document's topical richness above:
   - ~15–20 labels: `doe_cybersecurity_procurement_language_energy_delivery_2014.txt`
   - ~10–15 labels: `nistir_7621r1_small_business_fundamentals.txt`
   - ~8–10 labels: `nist_sp1300_csf20_small_business_quickstart.txt`
   - ~5–8 labels each: the two `data/sample_evidence/` synthetic documents
   This is a planning suggestion, not a requirement — label whatever practices you can genuinely
   judge with confidence, and skip the rest.
