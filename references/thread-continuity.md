# Thread Continuity

Use this reference when the work is expected to span multiple Codex turns or multiple threads, or when the repo does not yet have durable continuity docs.

## Goal

Create a repo-level continuity layer so a fresh Codex thread can resume work without depending on hidden model memory or silent compaction.

## Required Files

Use these files at the repo root:

- `README.md` as the entry point
- `CODEX_HANDOFF.md` as the running state and recap file

## README Rules

- Never overwrite or replace a useful existing `README.md`.
- Preserve the existing title, project description, overview, table of contents, badges, and main documentation structure.
- Merge continuity guidance into the existing file with the smallest possible diff.
- Add a short project title and description near the top if they are missing.
- Add a `Start Here` section near the beginning.
- When the README already has a title and opening summary, insert the `Start Here` block immediately after that top section instead of replacing content.
- If the README already has a comprehensive introduction, append the `Start Here` block after the title and first intro paragraph, not by rewriting the introduction.
- If the README already contains a `Start Here` or resume section, update it in place instead of duplicating it.
- In that section, tell a future Codex thread to read `CODEX_HANDOFF.md` first.
- State that the handoff must contain:
  - what has been built in Dataverse / Power Platform / Plugin so far
  - the current live environment and repo state
  - the current architecture decisions
  - open issues and recommended next steps

Suggested `Start Here` block:

```md
## Start Here

If you are resuming this work in a fresh Codex thread, read:

`CODEX_HANDOFF.md`

That handoff contains:

- what has been built in Dataverse / Power Platform / Plugin so far
- the current live environment and repo state
- the current architecture decisions
- open issues and recommended next steps
```

## CODEX_HANDOFF Rules

Create or update `CODEX_HANDOFF.md` at repo root.

Minimum sections:

1. what has been built in Dataverse / Power Platform / Plugin so far
2. the current live environment and repo state
3. the current architecture decisions
4. open issues and recommended next steps

Recommended extra sections:

- purpose
- validation state
- resume checklist

## What To Record

- Separate repo work from live Dataverse execution. Do not imply a deployment happened if it did not.
- Record current environment facts only when known and safe to store.
- Include concrete repo state such as important paths, current git status, solution names, prefixes, build results, or validation results when relevant.
- Capture decisions that a future thread would otherwise need to rediscover.
- Record blockers, caveats, and deferred work explicitly.
- Never store secrets, tokens, passwords, or session material.

## Update Triggers

Refresh `CODEX_HANDOFF.md` when:

- the user asks for a recap or handoff
- a major milestone is completed
- architecture or repo structure changes
- live environment work is executed
- an important blocker or caveat is discovered
- the thread becomes long enough that continuity risk is increasing

## Notify Before Compaction

Do not rely on silent auto-compaction as the primary continuity mechanism.

Important limitation:

- exact context percentage is not exposed, so do not claim you can see `100%` precisely
- instead, use a conservative heuristic based on thread length, number of decisions, number of touched files, or how much recap would be needed if the thread restarted

When that heuristic indicates context is getting tight:

1. tell the user that context is getting tight
2. update `CODEX_HANDOFF.md`
3. then continue or recap as needed

Suggested user-facing wording:

`Context is getting tight. I’m updating CODEX_HANDOFF.md before we continue so the repo stays resumable in a fresh thread.`
