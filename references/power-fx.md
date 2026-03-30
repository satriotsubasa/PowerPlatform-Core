# Power Fx

Use this reference when the task is about analyzing, debugging, or improving Power Fx formulas.

## Scope

- Canvas app formulas
- Command formulas
- Formula snippets used in app logic reviews
- Delegation-risk review
- Reliability and maintainability review

## Preferred Helper

- `scripts/debug_power_fx.py`

Use it when you need:

- function inventory
- delegation-risk checks
- missing `IfError` review for data writes
- maintainability warnings for large or deeply nested formulas
- rewrite hints and test-case suggestions

## Operating Rules

- Treat the helper as a heuristic reviewer, not a full compiler.
- Be explicit when a delegation warning depends on the actual data source.
- Prefer structured review output:
  - findings
  - rewrite hints
  - test cases
- Do not claim a formula is safe for delegation unless the underlying connector and data source are known.

## Good Uses

- review a long `OnSelect` formula
- flag `Patch` or `SubmitForm` without `IfError`
- highlight `Search`, `Distinct`, `ForAll`, `in`, or `exactin`
- propose test cases for blank values, permissions, large datasets, and null lookups
