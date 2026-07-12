# Clinical Pathway Case System 2.0.0

A repository-governed system for producing and displaying clinician-reviewed AMC-style cases with an ADHD-oriented reasoning layer.

## Architecture

```text
Curriculum + current Australian sources
            ↓
Case Builder Custom GPT
            ↓
Canonical clinical case
            ↓
Human case review and lock
            ↓
Reasoning Builder Custom GPT
            ↓
ADHD reasoning layer
            ↓
Independent Auditor + human review
            ↓
Codex validation and learner export
            ↓
Static website
```

## Core simplification

The normal authoring input is one exact case command:

```text
BUILD_CASE CP-P001-C001
```

The system resolves phase, pattern, evolution slot, station rules, failure modes, and source policy from the repository. The user does not duplicate those details in another form.

## Current release state

```text
Generation: frozen
Clinical cases generated: 0
Study-ready cases: 0
Website renderer: ready
```

## Start

1. Read `START_HERE.md`.
2. Build the three Custom GPTs using `gpts/FINAL_UPLOAD_CHECKLIST.md`.
3. Open the repository in Codex and use `CODEX_START_PROMPT.md`.
4. Use `CODEX_RUNBOOK.md` for the first authorised case.

A technical pass is not clinical approval. The website only accepts learner exports that passed source, audit, and named human gates.
