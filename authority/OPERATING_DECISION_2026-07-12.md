# Operating decision

**Date:** 12 July 2026  
**Decision status:** active

The authoring workflow must derive case context from the repository and the selected curriculum entry.

The operator must not be required to re-enter data already present in the system.

The operational flow is:

```text
explicit case command
→ repository-derived context
→ automatic preflight
→ case generation
```

If repository facts conflict, return HOLD with the exact conflict.

If an essential clinical fact cannot be supported by current sources, return HOLD with the exact unsupported claim.

This decision supersedes any earlier workflow that required a separate manually prepared preflight object.
