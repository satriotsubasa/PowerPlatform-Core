# Solution Standards

Use this reference when the task is about reviewing whether a repo or solution shape matches the intended standards and conventions.

## Preferred Helper

- `scripts/review_solution_standards.py`

## What It Should Review

- continuity docs such as `README.md` and `CODEX_HANDOFF.md`
- project-profile presence on hybrid or code-centric enterprise repos
- publisher-prefix inference quality
- ambiguity between main live solutions and supporting local solutions
- PCF manifest and wrapper solution version alignment
- generator-owned `*.Data` project boundaries
- `Reference` versus `Dataverse` folder intent

## Expected Output

- concise findings
- severity
- direct recommendations
- overall risk level

## Operating Rules

- Prefer actionable findings over generic advice.
- Treat `Reference` as docs-only unless the user explicitly says otherwise.
- Treat namespaced `*.Data` projects as generator-owned.
- Flag missing project profiles on hybrid enterprise repos as a standards risk, not a fatal error.
