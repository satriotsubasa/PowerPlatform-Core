---
name: document-generation
description: >
  Use for ANY Dataverse document-generation task built on Word Templates — inventory the
  content controls in a `.docx`/`.dotx` template, map placeholders to data, and plan a
  template-aware change before editing the template blindly. Fires whenever the user mentions
  a Word Template, document generation, content controls, placeholder or merge-field mapping,
  document-definition records, "why is this field blank in the generated doc", "add a placeholder
  to the template", "what tags does this template use", or a document-generation plug-in — even
  if no helper is named. It treats `Word Templates/` as first-class source, surfaces duplicate
  tags, missing required placeholders, and unused controls, and points at the `*.Business`,
  `*.Plugins`, and `*.Data` touchpoints a placeholder change implies. Run the live-mutation
  preflight from the `powerplatform-core` orchestrator before any live template or component write.
---

# Document Generation — Word Templates and Placeholder Mapping

This skill handles Power Platform document generation that uses Word Templates and content controls. It inventories the content controls inside `.docx`/`.dotx` templates, maps requested placeholders against what the template actually exposes, and plans template-aware changes — flagging duplicate tags, missing required placeholders, and unused controls before anyone edits a template blindly. It treats `Word Templates/` as a first-class source area and connects a placeholder change to the `*.Business`, `*.Plugins`, and document-definition data it depends on. It is intentionally generic about environment, publisher prefix, solution name, and folder layout — discover those per task.

## When to use this

- The user wants to know which content controls, tags, or aliases a template contains.
- A placeholder or merge field needs to be added, renamed, or remapped, and you need to know what it touches.
- A generated document has a blank or wrong field and you need to map the placeholder back to its data source.
- The user wants required-versus-optional placeholders validated against a template before a change.
- You are scoping a document-generation change across `Word Templates`, `Business`, `Plugins`, and `Data` source areas.

Route here from the `powerplatform-core` orchestrator. For solution packaging or promotion of templates and related components, use the `solution-alm-delivery` sibling skill.

## Helpers

The helpers live in the plugin's `scripts/` directory at the plugin root, not in this skill folder. Resolve the plugin root and invoke them like:

- `python "$CLAUDE_PLUGIN_ROOT/scripts/inspect_word_templates.py" --path <template-or-dir>` (Claude Code)
- `python "$CODEX_PLUGIN_ROOT/scripts/inspect_word_templates.py" --path <template-or-dir>` (also exposed as `$PLUGIN_ROOT`)
- Installed standalone / unsure: the `scripts/` folder sits beside this skill bundle — invoke by its path within the install.

| Helper | Purpose |
| --- | --- |
| `inspect_word_templates.py` | Inspect `.docx`/`.dotx` files and summarize their content controls. Defaults to the inferred `Word Templates` area; pass `--path` for a specific file or directory, `--recurse` for a directory tree, and `--summary-only` for per-file summaries without full control detail. Read-only inventory. |
| `plan_document_generation.py` | Plan a template-aware document-generation change from a `--spec` (template path or name, placeholder mappings, required-versus-optional placeholders, and entity/document-definition context). Returns current content controls, duplicate tags and aliases, mapped placeholders, missing required placeholders, unused controls, and the `Word Templates`/`Business`/`Plugins`/`Data` source-area touchpoints. Planning only. |

## Domain workflow

1. **Inventory the template first.** Run `inspect_word_templates.py` against the real template so you work from the actual content controls, tags, and aliases rather than assumptions.
2. **Plan before editing.** Run `plan_document_generation.py` with the requested placeholder mappings to see mapped placeholders, missing required placeholders, duplicate tags, and unused controls — plus the source-area touchpoints the change implies.
3. **Trace meaning changes to their source.** When a placeholder changes meaning, inspect the related `*.Business`, `*.Plugins`, and document-definition data before editing the template, rather than changing the tag in isolation.
4. **Keep templates source-controlled.** Treat `Word Templates/` as the deployable source; do not treat `Reference/` copies of templates as deployable source by default.
5. **Hand off structural redesign with judgment.** Inspection and planning are helper-backed; creating or redesigning `.docx` structure still needs repo-specific judgment and should stay review-driven until a stronger repeated pattern emerges.

## Safety and decision rules

- **`Word Templates/` is first-class source; `Reference/` is not.** Plan and edit against the deployable template, not a reference copy.
- **Do not retag blindly.** A placeholder is a contract with the generation logic — confirm the `*.Business`/`*.Plugins`/document-definition side before renaming or remapping a tag.
- **Surface duplicates and gaps explicitly.** Report duplicate tags/aliases, missing required placeholders, and unused controls instead of silently editing around them.
- **Keep structural redesign review-driven.** Lean on the helpers for inspection and mapping; treat new `.docx` structure as repo-specific work that needs explicit review.
- **Preflight gate.** Run the mandatory live-mutation preflight from the `powerplatform-core` orchestrator before any live template or related component write. Do not restate the full preflight here — invoke it there.

## References

- `references/document-generation.md` — primary helpers, operating rules, template planning inputs, what the planning helper returns, and the current helper-versus-judgment boundary.
