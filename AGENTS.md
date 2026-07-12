# Codex operating instructions

## Mission

Operate the Clinical Pathway repository. Do not become the clinical author.

The three Custom GPTs create the canonical case, the ADHD reasoning layer, and the independent audit. Codex validates, archives, versions, stores, exports, indexes, tests, and deploys their outputs.

## Read first

Before changing the repository, read in this order:

```text
1. authority/CASE_AUTHORING_STANDARD_v2.md
2. authority/OPERATING_DECISION_2026-07-12.md
3. registries/curriculum.json
4. registries/source-policy.json
5. schemas/
6. CODEX_RUNBOOK.md
7. repo/manifest.json
8. repo/queue/case-queue.json
```

## Generation freeze

Generation is frozen when `repo/queue/case-queue.json` contains:

```json
"generation_frozen": true
```

Do not generate, commission, or simulate a clinical case while frozen.

A case may start only after the user gives the exact command:

```text
BUILD_CASE [case_id]
```

Record it with `scripts/manage_queue.py start`. Do not infer authorisation from discussion, planning, or file upload.

## No duplicate intake

Do not ask the user to re-enter phase, pattern, slot, title, or project data already held in the repository.

Use `scripts/resolve_case.py` to resolve the selected curriculum and queue state automatically.

If repository data conflict, stop and name the exact conflict. Do not invent a clinical bridge.

## Component boundaries

```text
Case Builder GPT
Creates the complete canonical clinical case draft.

Reasoning Builder GPT
Creates the ADHD-oriented reasoning layer from a locked case.

Independent Audit GPT
Creates findings and an audit decision. It does not repair.

Codex
Runs deterministic repository operations only.
```

Codex must not:

- invent clinical content
- alter a clinical claim, urgency, dose, investigation, escalation, or disposition
- set a human review to pass
- pretend a source was archived
- merge a provisional registry patch without named human approval
- expose hidden authoring or audit data on the learner website

## Artifact workflow

Use these locations:

```text
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

Never overwrite a locked artifact. Increase semantic version after any meaning change.

## Validation rule

After each artifact arrives:

1. Validate schema and cross-references.
2. Compute deterministic hashes.
3. Archive exact source URLs and verify file hashes.
4. Route defects to the responsible GPT.
5. Preserve the exact registry snapshot used for reasoning.
6. Export only after all required audit and human gates pass.
7. Rebuild the learner index.
8. Run browser smoke tests.

## Website rule

The website reads only `website/data/index.json` and learner-export JSON files.

Never deploy canonical cases, source files, registries, audit reports, reviewer records, or hidden assessment guides.

## Stop conditions

Stop with a precise HOLD when:

- generation is frozen
- the case is not durably authorised
- a case ID is absent from the curriculum
- a high-risk claim lacks adequate support
- an archived source file is missing or has the wrong hash
- hashes or registry bindings disagree
- a human approval is absent
- an audit contains an open finding
- the learner export fails validation
