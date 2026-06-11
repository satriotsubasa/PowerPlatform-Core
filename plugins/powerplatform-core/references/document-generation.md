# Document Generation

Use this reference when the task is about `Word Templates`, content controls, placeholder mapping, or document-generation plug-in behavior.

## Primary Helpers

- `scripts/inspect_word_templates.py`
- `scripts/plan_document_generation.py`

## Operating Rules

- Treat `Word Templates/` as a first-class source area when the repo uses document templates for generation logic.
- Do not treat `Reference/` copies of templates as deployable source by default.
- When a placeholder changes meaning, inspect the related `*.Business`, `*.Plugins`, and document-definition data before editing the template blindly.

## Template Planning Inputs

Typical planning input includes:

- template path or template name
- placeholder mappings
- required versus optional placeholders
- entity or document-definition context when known

## What The Planning Helper Returns

- current content controls
- duplicate tags and aliases
- mapped placeholders
- missing required placeholders
- unused controls
- source-area touchpoints for `Word Templates`, `Business`, `Plugins`, and `Data`

## Current Boundary

- Template inspection and planning are helper-backed.
- Creating or redesigning `.docx` template structure still needs repo-specific judgment and should stay review-driven until a stronger repeated pattern emerges.
