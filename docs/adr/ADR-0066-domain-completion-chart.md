# ADR-0066: A domain completion chart, and the number it is not allowed to draw

**Status:** Accepted
**Sprint:** 23
**Deciders:** Fraz Ahmed
**Related:** ADR-0012 (the dashboard's situation/complication/resolution structure and its refusal to
fabricate numbers), ADR-0010 (NIST CSF has no native maturity concept), ADR-0030 (NOT_APPLICABLE
practices), ADR-0057 (a finding needs evidence before it moves anything), ADR-0009 (untranscribed
domains), ADR-0016 (the frontend's one dependency-conflict story), ADR-0065 (the other half of the
same tester's report), R-15

## Context

The same tester who reported the evidence queue also reported that the dashboard is plain text and
numbers with no visuals, and asked for a domain completion bar chart.

That is a fair request and the dashboard has the data. The entire decision is *which* number the bars
are drawn from, because the obvious candidate is wrong in a way that would be very hard to notice
afterwards.

## Why not `domain_scores`

`DashboardReport.domain_scores` is a `dict[str, float]`, one entry per domain, already computed and
already on the wire. Binding bars to it would take about ten minutes and would be a real defect.

Its meaning depends on the framework's scoring model. Under `cumulative_mil` (C2M2) it is an
**ordinal maturity level, 0–3**. Under `coverage` (NIST CSF 2.0, which has no native maturity
concept, ADR-0010) it is a **fraction, 0.0–1.0**. Drawing both as bar length puts a maturity level
and a percentage on one axis, which is exactly what R-15 records: *"a cumulative_mil score and a
coverage score mean different things and must never be blended into one fabricated number."*
`OverallSummary` already refuses to average domain scores on a cumulative_mil framework for the same
reason, and `ScoreHeadline` renders the server's sentence verbatim rather than re-deriving anything.
A chart that quietly did the blend would undo both.

Worse, it would be plausible. MIL2 out of 3 renders as a two-thirds bar and looks entirely
reasonable. Nothing about the output would announce that a reader is looking at an ordinal scale
stretched into a proportion.

## Decision

**Bars are `met_practices` over `total_practices`, applicable practices only.** That ratio means the
same thing under both scoring models, which is what makes it chartable at all. The denominator
excludes NOT_APPLICABLE practices (ADR-0030) — the same denominator `compute_domain_coverage` uses —
so the bar and the score printed beside it cannot disagree about what was counted.

**Computed server-side, as `DashboardReport.domain_progress`.** `DashboardTab`'s own contract is that
it re-derives nothing, and a percentage assembled in the browser is a second implementation of the
applicable-practice denominator whose first disagreement would be with the score next to it.

**Not derived from `complication`.** That section lists domains with at least one unmet practice,
which is correct for "where gaps remain" and wrong for a chart: a completion chart that silently
drops the finished domains overstates what is outstanding and hides the best news in the assessment.

**The domain's real score travels alongside each bar**, labelled in its own units — `MIL2`, or
`50% coverage` — so the chart shows completion and score as two facts rather than implying they are
one.

**`blocking_mil` and `blocking_practice_count` are the point of this ADR.** Under a cumulative
framework, completion and score are not the same shape: MIL2 requires *every* MIL1 practice, so a
domain at 9 of 10 practices met is a 90% bar sitting next to MIL0 when one MIL1 practice is missing.
That is correct behaviour and it reads as a bug. The report therefore names which level is blocked
and how many practices are holding it, and the chart renders that under the bar: *"1 practice(s) at
MIL1 still unmet, so this domain cannot score above MIL0 however complete the bar looks."* A reader
who would have filed a defect instead learns what to do next.

These fields mirror `compute_domain_mil`'s rule — walk the levels in order, stop at the first not
fully performed — rather than reimplementing its result. They are `None` on a coverage framework and
`None` at the top level, because in both cases there is no gate left to name.

**Unpopulated domains are omitted, not charted at zero.** A domain whose practices have not been
transcribed into `framework_mapping/` yet (ADR-0009) has nothing to be complete or incomplete about,
and an empty bar would report an absence as a gap. `Situation.unpopulated_domains` already names
them. A domain whose every practice is NOT_APPLICABLE is omitted for the same reason: `0 of 0` reads
as "nothing done" rather than "nothing applies."

**Worst domain first.** The chart is read to decide where to work next, and the domain missing the
most practices is that answer. Ties break on short code so the order is stable between renders.

**Plain elements, no charting library.** Ten bars do not justify a dependency, and this repo's one
peer-conflict story (ADR-0016) is enough. Each bar carries an `aria-label` stating the same numbers
in words, because a bar is the one form of this information a screen reader cannot recover.

## Consequences

- The dashboard has a visual, and it is one that survives being read carefully.
- `DashboardReport` gains a field. It is additive and defaulted, so nothing that consumed the report
  before needs to change. The seal (ADR-0060) covers the assessment record, not the report, so
  nothing about tamper-evidence is affected.
- The chart sits below `ScoreHeadline` deliberately. That component renders the server's
  scoring-model-aware sentence, which is what the assessment actually claims; the chart is the shape
  of it. Bars first would make the picture the claim.
- 22 new tests: 11 on the report builder, where the denominator and the gate are decided, and 11 on
  the component, where the reading is.
- The MIL-gate explanation is a genuinely new piece of information in the product. It was previously
  derivable only by opening a domain and comparing practice MILs by hand.

## What this does not do

**The exports do not get the chart.** The PDF and XLSX carry the same *numbers* through
`complication` and `so_what`, but not this visual and not the MIL-gate sentence. That is a real
inconsistency between screen and document, disclosed here rather than discovered: a reviewer who
reads the gate explanation on screen and then sends the PDF has sent something that does not contain
it. Adding it is a separate piece of work in the report renderers.

**A bar is still a summary.** Practice counts weight every practice equally, which is true of the
underlying scoring model too, but it means a domain missing one hard practice and a domain missing
one trivial one look identical here. The gap list below the chart is where that detail lives.

## Alternatives considered

**Chart `domain_scores` and normalise MIL to a 0–1 scale.** Rejected: dividing an ordinal by 3 to
make it fit an axis is the fabrication R-15 names, and it would make MIL1 and MIL2 look like 33% and
67% of something.

**Two different chart types per scoring model** — bars for coverage, a stepped indicator for MIL.
Rejected as more machinery than the problem needs, and it would make the two frameworks
incomparable at a glance for no gain. Showing one honest ratio plus the real score in its own units
achieves the same without a second chart to maintain.

**Compute the percentages in the frontend from `complication`.** Rejected twice over: it re-derives
numbers the dashboard is supposed to receive, and `complication` does not contain the fully-met
domains.

**Add a charting library.** Rejected — see above. Revisit if the dashboard ever needs a chart type
that is genuinely awkward in markup, which a horizontal bar per domain is not.

**Omit the MIL gate and let the score speak for itself.** Rejected: this is the whole reason the ADR
exists. A 90% bar beside MIL0 with no explanation is worse than no chart, because it invites the
reader to trust whichever of the two numbers they already believed.
