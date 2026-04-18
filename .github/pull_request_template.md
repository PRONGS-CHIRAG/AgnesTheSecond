# Pull Request

## Summary

<!-- What does this PR do? Link to the plan stage or issue. -->

## Schema-version checklist

Any change to a persisted Pydantic/JSON/Zod schema **must** bump its version
constant and add a migration path. Tick all that apply (or mark N/A):

- [ ] `TAXONOMY_VERSION`
  (`chirag/src/agnes/canonicalization/taxonomy.py`)
- [ ] `SUBSTITUTES_SCHEMA_VERSION`
  (`chirag/src/agnes/models/substitutes.py`)
- [ ] `EVIDENCE_SCHEMA_VERSION`
  (`chirag/src/agnes/models/evidence.py`)
- [ ] `ASSESSMENT_SCHEMA_VERSION`
  (`chirag/src/agnes/models/assessment.py`)
- [ ] `RISK_SCHEMA_VERSION`
  (`chirag/src/agnes/models/risk.py`)
- [ ] `RECOMMENDATION_SCHEMA_VERSION`
  (`chirag/src/agnes/models/recommendation.py`)
- [ ] `PROCUREMENT_SCHEMA_VERSION`
  (`chirag/src/agnes/models/procurement.py`)
- [ ] `CHAT_SCHEMA_VERSION`
  (`chirag/src/agnes/models/chat.py`)
- [ ] Frontend Zod schemas in `chirag/frontend/src/lib/schemas/*`
- [ ] Migration / upgrade script added under `chirag/scripts/` if existing
      artifacts need to be rewritten
- [ ] `.cache/` entries invalidated or documented

## Test plan

- [ ] Unit tests updated (`uv run --with pytest pytest chirag/tests -q`)
- [ ] Phases re-run from clean state
      (`bash chirag/scripts/run_all_phases.sh --seed-mock`)
- [ ] `bash chirag/scripts/check_no_taim_imports.sh` passes locally

## Reviewer notes

<!-- Call out anything tricky, e.g. cache invalidation, artifact deletions,
     env-var changes, schema migrations. -->
