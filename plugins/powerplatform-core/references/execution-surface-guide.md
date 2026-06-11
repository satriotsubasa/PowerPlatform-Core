# Execution Surface Guide

Use this reference when deciding which implementation surface should own a change.

## Core Rule

Choose the lightest supported surface that can enforce the requirement at the scope the user actually needs.

Keep presentation and configuration work in metadata when possible. For executable logic, this skill is intentionally code-first: do not choose Dataverse Business Rules as an implementation surface. Use client script for form-scoped behavior, and use synchronous plug-ins or custom APIs when the logic belongs on the server.

Do not escalate to plug-ins, PCF, or custom APIs just because they are powerful. Do not keep a change in client script or metadata if the requirement actually needs server-side enforcement or a reusable component surface.

## Quick Decision Map

### Presentation-only app or metadata changes

Use [dataverse-metadata.md](dataverse-metadata.md) when the task is mainly:

- table, column, relationship, form, view, chart, icon, app-module, or sitemap configuration
- exposing an existing table, view, dashboard, or page inside a model-driven app
- changing visible columns, field placement, navigation, or default metadata behavior

Do not jump to JavaScript or plug-ins for a request that is only about what the user can see or open.

### Form script vs plug-in

Use the smallest surface that matches the requirement:

- Form script:
  - default choice for client-side executable logic in this skill
  - form-session behavior such as conditional required level, visibility, filtering, notifications, and supported `Xrm.WebApi` calls
  - richer client interaction, conditional UX, dynamic filtering, custom notifications, or supported `Xrm.WebApi` calls
  - logic that is specific to a form session or user interaction path
  - requirements that do not need server enforcement
- Synchronous plug-in:
  - logic that must be enforced for all entry points, not only one form
  - transaction-bound validation or derived data that must stay correct on create or update regardless of caller
  - rules that should hold for imports, API calls, flows, integrations, and UI edits alike

If the same validation matters outside one form, do not leave it only in a form script. Move it to a synchronous plug-in. If a requirement would historically fit a Dataverse Business Rule, this skill still prefers form script for client-only behavior or a synchronous plug-in for shared enforcement.

### Plug-in vs Custom API

Use a plug-in when:

- the logic belongs on an existing table message such as create, update, delete, assign, or retrieve
- the behavior is part of standard table lifecycle enforcement

Use a custom API when:

- callers need an explicit named operation
- the action has a request and response contract
- the behavior should be invoked intentionally from code, Power Automate, or another integration instead of piggybacking on a table event

### Web resource vs PCF

Use client script or lightweight HTML web resources when:

- the requirement is small, form-specific, or page-specific
- the UI does not need a reusable high-interaction component model
- supported model-driven form APIs are enough

Use PCF when:

- the requirement is a reusable field or dataset control
- the UI needs richer rendering, interaction, or binding than scripts and HTML web resources should reasonably own
- the same component should be deployed across multiple forms, views, or apps as a supported control

Do not use a PCF control just to place a button, a small notification, or a one-form helper that client script can already handle cleanly.

### Power Automate vs plug-in

Use solution-aware cloud flows when:

- the process is asynchronous, orchestration-heavy, connector-heavy, approval-based, or cross-system
- eventual consistency is acceptable
- the main value is process automation rather than transaction-bound enforcement

Use a synchronous plug-in when:

- the rule must succeed or fail inside the Dataverse transaction
- the result must be consistent immediately at save time
- the operation cannot tolerate asynchronous lag

## Common Patterns

### Add a new field and show it in the app

Usually:

1. metadata change
2. form placement
3. view or quick-find exposure if needed
4. app or sitemap exposure if the table itself is new

Do not stop after creating the column if the user clearly asked for a usable app surface.

### Require a field only in one form experience

Usually:

- form script

Do not use a plug-in unless the requirement must also hold outside that form.

### Validate a rule for all callers

Usually:

- synchronous plug-in

Optionally pair it with:

- client-side guidance for better user experience

The client layer can improve immediacy, but the server layer is the source of truth for shared enforcement.

### Launch a reusable server-side operation from Power Automate or code

Usually:

- custom API backed by a plug-in or other server implementation

Do not hide an explicit business operation inside an unrelated update message if the caller really needs a named action.

## Quick Create And Form-Component Cautions

- Quick create forms do not always mirror main-form libraries, layout, or event wiring. If a requirement mentions quick create, verify that the target behavior is actually bound there.
- A change that works on the main form may still be missing on quick create, card forms, or other specialized surfaces.
- Form-component or embedded-form patterns can make a field or subgrid appear in more than one visual context. Confirm whether the request is about the main form only or every place the component is reused.
- Do not assume one form script registration reaches every app surface automatically.

## Escalation Checks

Before choosing a heavier surface, ask:

- does the rule need server enforcement, or only user guidance?
- does it need to work for every caller, or only one form or app?
- is the requirement reusable enough to justify PCF or a custom API?
- can supported metadata or client APIs already solve it cleanly?

If those answers stay local and lightweight, prefer metadata or client customization over a new server component.
