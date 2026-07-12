# Repository operations

Use `CODEX_RUNBOOK.md` as the executable workflow.

## Durable folders

```text
repo/queue/
repo/cases/draft/
repo/cases/locked/
repo/reasoning/draft/
repo/reasoning/approved/
repo/audits/
repo/registry/
repo/registry/archive/
repo/sources/archive/
repo/website-data/
```

## Canonical names

```text
CP-P001-C001_v1.0.0_case-draft.json
CP-P001-C001_v1.0.0_case-locked.json
CP-P001-C001_v1.0.0_reasoning-draft.json
CP-P001-C001_v1.0.0_reasoning-approved.json
CP-P001-C001_v1.0.0_audit.json
CP-P001-C001_v1.0.0_registry-patch.json
CP-P001-C001_v1.0.0_learner.json
```

## Version rule

Never overwrite locked or approved artifacts. Increase the semantic version after a meaning change. Recompute every dependent hash and rerun all affected audits and reviews.

## Deployment boundary

Deploy only:

```text
website/index.html
website/app.js
website/styles.css
website/data/index.json
website/data/*_learner.json
```

Do not deploy canonical cases, archived clinical sources, reasoning registries, audit reports, or reviewer records.
