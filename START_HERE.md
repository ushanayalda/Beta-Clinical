# Start here

## What is complete

```text
Case curriculum: complete
Case authoring authority: complete
Case Builder specification: complete
Reasoning Builder specification: complete
Independent Auditor specification: complete
Repository contracts and validators: complete
Static website renderer: complete
Generation queue: complete and frozen
```

## What is intentionally absent

```text
Generated clinical cases: 0
Study-ready website cases: 0
```

No clinical content was generated during system construction.

## Setup sequence

### 1. Verify locally

```bash
python -m pip install -r requirements.txt
python scripts/validate_package.py
python -m unittest tests/test_system.py -v
python tests/browser_smoke.py
```

### 2. Create the three private Custom GPTs

Use:

```text
gpts/FINAL_UPLOAD_CHECKLIST.md
```

### 3. Open the repository in Codex

Give Codex:

```text
CODEX_START_PROMPT.md
```

### 4. Keep generation frozen

```bash
python scripts/manage_queue.py status
```

Expected:

```text
generation_frozen: true
```

### 5. Start only after the exact command

```text
BUILD_CASE CP-P001-C001
```

Codex records the command and resolves all repository context. The Case Builder then creates the canonical draft.

## Files that control the system

```text
authority/CASE_AUTHORING_STANDARD_v2.md
registries/curriculum.json
registries/source-policy.json
gpts/FINAL_UPLOAD_CHECKLIST.md
AGENTS.md
CODEX_RUNBOOK.md
schemas/
scripts/
website/
```
