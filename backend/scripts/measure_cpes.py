"""CPES measurement (Sprint 18, controlled-pilot readiness §F.3).
`CPES = 0.40 Stability + 0.30 Scalability + 0.30 Reusability`. Not part
of the application (see scripts/benchmark_scalability.py's module
docstring convention: this directory is for humans to run directly).
Run manually:

    cd backend && source .venv/bin/activate
    python scripts/measure_cpes.py --benchmark-json /path/to/benchmark_output.json

Computes each component from a real measurement taken at run time,
never from a number typed into a doc by hand:

- **Stability**: runs the real pytest suite (`pytest --junit-xml`) and
  reports the actual pass/fail/error/skip counts from that run.
- **Scalability**: reads a JSON file previously produced by
  `scripts/benchmark_scalability.py --output <path>`. Not re-run here —
  that script takes several minutes at the 1,000-document tier and this
  script is meant to be cheap to re-run on every change. If no
  `--benchmark-json` is given, this component is reported as
  "not measured this run", never estimated or carried forward silently.
- **Reusability**: counts the current number of framework definition
  YAML files under `framework_mapping/`. This is a raw current count,
  not a "frameworks added since MVP close" delta — that framing (used
  in `docs/architecture/02-controlled-pilot-readiness-audit.md` §F.3)
  is a historical fact tracked by this project's ADR trail
  (`docs/adr/`), not something this script derives from file listing
  alone, and it is not recomputed here.

Deliberately does **not** compute or print a single weighted CPES
number. Per the audit doc's own "do not inflate scores because test
count is high" discipline: a composite is only honest when every
component behind it is trustworthy, and the Scalability component
currently carries a disclosed, unresolved measurement (retrieval
latency at scale, ADR-0033) that this script has no way to evaluate
automatically. Collapsing three measurements of differing confidence
into one number would fabricate a precision this project doesn't have.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_FRAMEWORK_MAPPING_DIR = _BACKEND_ROOT.parent / "framework_mapping"


def measure_stability() -> dict:
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        junit_path = Path(tmp.name)
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", f"--junit-xml={junit_path}"],
            cwd=_BACKEND_ROOT,
            capture_output=True,
            text=True,
        )
        root = ET.parse(junit_path).getroot()
        # A single <testsuite> root or a <testsuites> wrapper, depending
        # on pytest version -- normalize to the first testsuite element.
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        total = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))
        passed = total - failures - errors - skipped
        return {
            "total": total,
            "passed": passed,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "pass_rate": (passed / total) if total > 0 else None,
        }
    finally:
        junit_path.unlink(missing_ok=True)


def measure_reusability() -> dict:
    yaml_files = sorted(
        p.name
        for p in _FRAMEWORK_MAPPING_DIR.glob("*.yaml")
        if p.name != "cross_framework_equivalence.yaml"
    )
    return {
        "total_frameworks_current": len(yaml_files),
        "framework_files": yaml_files,
        "note": (
            "Raw current count, not a delta since MVP close -- that historical framing "
            "is tracked in docs/adr/, not derived here."
        ),
    }


def measure_scalability(benchmark_json: Path | None) -> dict:
    if benchmark_json is None:
        return {
            "measured_this_run": False,
            "note": (
                "No --benchmark-json given. Run "
                "`python scripts/benchmark_scalability.py --output <path>` first, then pass "
                "that path here. Never estimated or carried forward silently."
            ),
        }
    data = json.loads(benchmark_json.read_text())
    return {
        "measured_this_run": False,
        "source_file": str(benchmark_json),
        "note": "Loaded from a prior benchmark_scalability.py run, not re-measured here.",
        "raw_results": data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--benchmark-json", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    print("Running the real pytest suite for Stability (this takes a few minutes)...", flush=True)
    result = {
        "stability": measure_stability(),
        "scalability": measure_scalability(args.benchmark_json),
        "reusability": measure_reusability(),
        "composite": None,
        "composite_note": (
            "Deliberately not computed. See this script's module docstring -- collapsing "
            "components of differing confidence into one weighted number would fabricate "
            "precision this project doesn't have."
        ),
    }
    print(json.dumps(result, indent=2))

    if args.output:
        args.output.write_text(json.dumps(result, indent=2))
        print(f"\nWrote results to {args.output}")


if __name__ == "__main__":
    main()
