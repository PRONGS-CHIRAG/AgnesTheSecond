#!/usr/bin/env bash
# End-to-end pipeline driver for the Agnes demo.
#
# Usage:
#   bash scripts/run_all_phases.sh [--seed-mock] [--skip-phase5] [--reports-dir PATH]
#
# Flags:
#   --seed-mock       Seed the mock procurement tables before running.
#   --skip-phase5     Skip Phase 5 (useful when TAVILY_API_KEY is unset).
#   --reports-dir D   Override outputs directory (default: outputs/reports).
#
# Environment prerequisites:
#   AGNES_OPENAI_API_KEY — required for Phases 4, 5, 6, 7
#   AGNES_TAVILY_API_KEY — required for Phase 5 only
#
# The script fails fast on any phase error (set -e). Each phase prints
# structured JSON on success so callers can tee the output.

set -euo pipefail

SEED_MOCK=0
SKIP_PHASE5=0
REPORTS_DIR="outputs/reports"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --seed-mock)      SEED_MOCK=1; shift ;;
    --skip-phase5)    SKIP_PHASE5=1; shift ;;
    --reports-dir)    REPORTS_DIR="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

export AGNES_REPORTS_DIR="$REPORTS_DIR"

run_phase() {
  local label="$1"; shift
  echo "==> ${label}"
  uv run python "$@"
}

if [[ "$SEED_MOCK" -eq 1 ]]; then
  run_phase "Phase 0: mock procurement seed" \
    scripts/seed_procurement_mock.py --apply --summary
fi

run_phase "Phase 1: schema + overlap" scripts/phase1_schema.py
run_phase "Phase 1: overlap report"   scripts/phase1_overlap.py
run_phase "Phase 2: taxonomy upgrade" scripts/phase2_upgrade_taxonomy.py

run_phase "Phase 4: candidate generation" scripts/phase4_candidates.py

if [[ "$SKIP_PHASE5" -eq 0 ]]; then
  run_phase "Phase 5: evidence enrichment" scripts/phase5_evidence.py
else
  echo "==> Phase 5 skipped (--skip-phase5)"
fi

run_phase "Phase 6: assessment"        scripts/phase6_assess.py
run_phase "Phase 6.5: risk register"   scripts/phase6_5_risks.py
run_phase "Phase 7: recommendations"   scripts/phase7_recommend.py

echo ""
echo "All phases complete. Reports in: ${REPORTS_DIR}"
ls -la "$REPORTS_DIR"
