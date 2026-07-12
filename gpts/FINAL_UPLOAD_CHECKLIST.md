# Final Custom GPT setup checklist

## GPT 1: Clinical Pathway Case Builder

Permanent Knowledge:

```text
authority/CASE_AUTHORING_STANDARD_v2.md
authority/OPERATING_DECISION_2026-07-12.md
registries/curriculum.json
registries/phases.json
registries/station-grammars.json
registries/failure-modes.json
registries/id-namespaces.json
registries/source-policy.json
schemas/canonical-case.schema.json
schemas/hold-report.schema.json
schemas/case-build-response.schema.json
```

Capabilities:

```text
Web Search ON
Data Analysis ON
All other capabilities OFF
```

Paste the instruction block from `CASE_BUILD_GPT_INSTRUCTIONS.md`.

The only normal generation command is:

```text
BUILD_CASE CP-P001-C001
```

No additional form or duplicate case specification is uploaded.

## GPT 2: Clinical Pathway ADHD Reasoning Builder

Permanent Knowledge:

```text
schemas/canonical-case.schema.json
schemas/reasoning-layer.schema.json
schemas/reasoning-registry.schema.json
schemas/registry-patch.schema.json
schemas/hold-report.schema.json
schemas/reasoning-response.schema.json
registries/id-namespaces.json
registries/visual-anchors.json
registries/failure-modes.json
```

Capabilities:

```text
Data Analysis ON
Web Search OFF
All other capabilities OFF
```

Per case:

```text
locked canonical case JSON
exact reasoning registry snapshot
```

Paste the instruction block from `REASONING_GPT_INSTRUCTIONS.md`.

## GPT 3: Clinical Pathway Independent Auditor

Permanent Knowledge:

```text
authority/CASE_AUTHORING_STANDARD_v2.md
registries/source-policy.json
registries/id-namespaces.json
registries/visual-anchors.json
registries/failure-modes.json
schemas/canonical-case.schema.json
schemas/reasoning-layer.schema.json
schemas/reasoning-registry.schema.json
schemas/audit-report.schema.json
schemas/hold-report.schema.json
schemas/audit-response.schema.json
schemas/learner-export.schema.json
```

Capabilities:

```text
Web Search ON
Data Analysis ON
All other capabilities OFF
```

Per audit:

```text
canonical case JSON
reasoning layer JSON
exact build-time reasoning registry snapshot
all archived source files named by the canonical case
previous audit report for a rerun only
```

Paste the instruction block from `INDEPENDENT_AUDIT_GPT_INSTRUCTIONS.md`.

## Boundary check

```text
Case Builder creates clinical content.
Reasoning Builder creates the learner reasoning layer.
Independent Auditor creates findings only.
Codex validates, archives, stores, exports, indexes, tests, and deploys.
Website displays approved learner exports only.
```
