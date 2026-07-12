# Operational repository

The repository is the durable authority. GPT conversations are temporary workers.

```text
queue authorisation
→ canonical draft
→ source archive
→ canonical review and lock
→ reasoning draft
→ independent audit
→ human reasoning approval
→ registry patch approval
→ learner export
→ website index
```

Generation is controlled by `queue/case-queue.json`.

The standard user action is one exact command. Repository context is resolved automatically. No duplicate case specification is maintained.
