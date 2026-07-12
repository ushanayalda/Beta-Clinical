# Static learner website

The website is a display layer only.

It loads:

```text
website/data/index.json
website/data/*_learner.json
```

It displays:

```text
Stem
Exact tasks
Task anchors
Reading and performance clocks
Complete script
Collapsed Hints
Local self-assessed progress
```

It does not load or display clinical source records, hidden assessment guides, reasoning registries, audits, reviewer details, or governance data.

The release package intentionally contains an empty learner index. Approved cases are copied into `website/data/` only after export validation.
