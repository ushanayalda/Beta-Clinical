# Custom GPT upload map

Use `FINAL_UPLOAD_CHECKLIST.md` as the authoritative list.

```text
CASE BUILDER
Permanent: authoring authority + curriculum + station/source registries + canonical schemas
Per build: no extra project form
Command: BUILD_CASE [case_id]

REASONING BUILDER
Permanent: reasoning schemas + visual and ID registries
Per build: locked canonical case + exact reasoning registry snapshot
Command: BUILD_REASONING

INDEPENDENT AUDITOR
Permanent: audit schemas + source and safety authorities
Per audit: canonical case + reasoning layer + registry snapshot + archived sources
Command: AUDIT_CASE
```

Generated artifacts are never uploaded as permanent Knowledge.
