# Sprint 7 — MBA and Consulting Interview Narrative

Continues the convention from Sprints 0-6: claims here are tied to what was actually built and found
this sprint, listed in `docs/consulting/sprint-07-deliverables.md`'s Change Log.

## MBA Applications

**Recognizing that "the same data, differently shaped" is a real design requirement, not a
shortcut to skip.** The obvious way to build PDF and XLSX export is to write one internal report
representation and render it twice — same headings, same order, just a different file extension.
That would have been less code. It also would have quietly under-served both of US-6.2's actual
audiences: a board member reading a fixed PDF narrative and a compliance lead who needs to filter
and sort a working spreadsheet do not want the same document. Treating "which artifact does this
specific stakeholder actually need" as a real question — not a solved problem once "export" is
scoped — is the same instinct that separates a client deliverable that gets used from one that gets
filed.

**A previous sprint's investment in a clean data boundary paid a measurable return, and that return
was worth naming, not just banking silently.** Sprint 6 built `DashboardReport` as a real, typed,
already-verified structure specifically so that report generation would become "a rendering problem
on top of already-correct data." Sprint 7 is the sprint where that bet was cashed in:
`export_service.py` contains zero scoring logic, only presentation. Recognizing and stating that the
architecture decision paid off as predicted — rather than treating it as obvious in hindsight — is
the kind of explicit before/after tracking a case team uses to show a client that an earlier
investment decision was actually validated, not just assumed to have worked.

**A library-level bug surfaced by testing, not by the live demo, and fixed by understanding the
mechanism rather than patching around the symptom.** fpdf2 raised `Not enough horizontal space to
render a single character` partway through writing consecutive text blocks. The fast fix would have
been to catch the exception and retry, or to shrink margins until the error stopped appearing. The
actual fix required understanding why the library's cursor position wasn't where the code assumed it
was after a `multi_cell` call, and pinning that position explicitly everywhere rather than relying on
a default that turned out not to hold. Diagnosing root cause instead of suppressing the symptom is a
small technical episode with a direct case-interview analogy: a client's KPI dashboard showing wrong
numbers intermittently is rarely fixed well by adding a rounding tweak where the wrong number shows up.

## Consulting Interviews

**Consulting competency demonstrated:** matching a deliverable's format to its actual audience
instead of defaulting to one format rendered twice. The PDF-narrative/XLSX-data-appendix split in
ADR-0013 mirrors how a case team decides a partner-facing deck and a working data-tab appendix are
two different documents serving two different readers, not one document exported in two file types.

**Business problem solved:** the platform's dashboard (Sprint 6) was API-only — genuinely useful to
this project's own developer, not yet useful to the CISO, compliance lead, or auditor named in
`PROJECT_CHARTER.md`'s stakeholder map, none of whom will ever call an API directly. Sprint 7 is the
sprint where the platform's output actually leaves the system as something a non-technical
stakeholder can open.

**Measurable value created:** two new, live-verified export endpoints; a genuine implementation bug
found and fixed via the test suite before it could surface in front of a stakeholder; 9 new tests (7
unit, 2 end-to-end); one ADR resolving four real design questions (recompute-or-render,
persist-or-not, one-layout-or-two, and a font-encoding edge case); and a clean architectural payoff
from Sprint 6's data-modeling decision, made explicit rather than left as an unstated assumption.

**How this would be presented to a client:** as a working export feature delivered with an explicit
statement of its one disclosed limitation — a downloaded report is a snapshot, not a live view, and
nothing server-side tracks which snapshot is in circulation — rather than a claim of "fully
automated reporting" that quietly omits that caveat. The mitigating detail (a printed generation
timestamp in both formats) is also stated plainly, the same way a case team discloses a model's
known limitation alongside the mitigant that makes it acceptable, rather than either hiding the
limitation or overselling the fix.

## STAR story draft

**Situation:** Sprint 6 delivered a real, structured executive dashboard, but it was reachable only
via an API call — useless to the actual stakeholders (a board, a CISO, an auditor) who would never
call an endpoint directly. US-6.2 asked for a downloadable PDF and XLSX, and the fast path was to
design one report layout and render it into both formats.

**Task:** Design and ship a PDF/XLSX export that actually serves two different real audiences
(a board reading a fixed narrative; a compliance lead needing a working spreadsheet), without
recomputing any of Sprint 6's already-verified scoring/gap logic, without silently crashing on the
transcribed framework text's occasional non-ASCII characters, and without introducing new
server-side state the project had no concrete need for yet.

**Action:** Built `export_service.py` as a pure rendering layer over the existing `DashboardReport`,
deliberately designing PDF and XLSX as two different views — prose in dashboard order for PDF, four
flat filterable sheets for XLSX — rather than one layout in two formats. Added an explicit Latin-1
safety translation for the small set of punctuation characters (em/en dashes) present in the
DOE/NIST source text, so report generation cannot crash on content it didn't anticipate. During test
writing, hit a real fpdf2 exception (`Not enough horizontal space to render a single character`)
caused by the library's text-cursor position not returning to the left margin between consecutive
text blocks; diagnosed the actual mechanism and fixed it by pinning cursor position explicitly on
every write, rather than working around the symptom. Chose not to persist generated reports
server-side, disclosing the resulting point-in-time-snapshot limitation as a new, named risk (R-21)
rather than leaving it unstated.

**Result:** Both export endpoints verified live against a running server — a PDF whose extracted
text (read back with `pypdf`) contains the real assessment name and the real 71-practice gap list,
and an XLSX (read back with `openpyxl`) with four correctly-populated sheets and the correct
resolution ranking. 9 new tests, all passing (139 total); one ADR documenting four resolved design
questions; and a Sprint 6 architectural bet (a clean, typed `DashboardReport`) whose payoff is now
directly demonstrated rather than only claimed.
