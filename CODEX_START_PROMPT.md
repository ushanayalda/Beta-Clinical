# Prompt to give Codex after opening the repository

```text
Read AGENTS.md and CODEX_RUNBOOK.md first.

Do not generate clinical content.
Do not unfreeze generation.

Validate the complete Clinical Pathway package, confirm that the case queue is frozen, confirm the learner index is empty, and report only:
1. technical readiness
2. generation state
3. Custom GPT setup state
4. website display state
5. exact blocking defects, if any

Do not redesign the architecture.
```

When ready to start one case, use a separate instruction:

```text
BUILD_CASE CP-P001-C001
Record this exact authorisation in the queue, resolve the repository context, and stop at the Case Builder handoff.
```
