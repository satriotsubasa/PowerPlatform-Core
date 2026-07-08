# Roadmap

Living document. Informed by the [Dataverse MCP comparison](comparison-dataverse-mcp.md) (July 2026): PowerPlatform-Core's moat is **repo-first delivery with enforced safety** — the roadmap hardens that moat instead of competing with the MCP on conversational data access.

## v1.5.0 — "Trust & Interop"

Theme: make the safety story *technically enforced* (not just skill-instructed), add the unattended-auth path nobody else has, and formally embrace the Dataverse MCP as a complementary channel.

> **Status (July 2026):** Phases A–D implemented on `feature/v1.5-trust-interop` and green under `verify_repo.py`. Pending maintainer **live verification** of service-principal auth (Phase A) and preflight-token gating (Phase B) before tag + release.

### Phase A — Service-principal / client-credentials auth (highest leverage)

Neither this plugin nor the Dataverse MCP documents a non-interactive path today; first mover wins CI/CD, scheduled agents, and headless verification.

- `DataverseOps`: extend `Connect()` with `--auth-flow clientsecret` (`--app-id`, `--tenant-id`, secret read from the `DATAVERSE_CLIENT_SECRET` env var — never a CLI argument) and `--auth-flow certificate` (`--certificate-path`, password via env var). MSAL confidential-client token provider alongside the existing public-client path.
- Python: `resolve_live_connection()` gains a service-principal mode (skips PAC-profile defaulting and the auth dialog); flag plumbed through every live helper.
- Docs: application-user setup (the `platform-administration` skill already documents `pac admin create-service-principal`); secret-hygiene guidance.
- Tests: arg/flow plumbing unit tests; live verification against a real app user before release.

**Done when:** `read_data.py`/`upsert_data.py` run end-to-end with an application user and no human interaction.

### Phase B — Enforced preflight tokens

Convert the plugin's best differentiator from procedural to technical. Today a harness that ignores SKILL.md can call mutating helpers directly.

- `validate_delivery.py --preflight-spec` additionally emits a short-lived preflight token (hash of spec + expiry) to a well-known temp path.
- Highest-risk mutating helpers require `--preflight-token` (or auto-discover the fresh token) before any live write: `deploy_solution.py`, `push_plugin.py`, `register_plugin_headless.py` / `register_plugin_package_headless.py`, `update_flow.py`, `delete_data.py`. Explicit `--no-preflight` escape hatch that logs loudly.
- Remaining mutating helpers follow in v1.6 once the pattern is proven.

**Done when:** the five listed helpers refuse a live mutation without a valid token, with tests asserting the refusal.

### Phase C — Dataverse MCP interop

- Orchestrator + `data-operations` SKILL.md gain explicit routing rules: if the Dataverse MCP is connected, prefer it for interactive NL exploration (`search`/`describe`/`read_query`); use plugin helpers for anything paged, keyed, verified, solution-aware, or mutating; degrade gracefully around known MCP limits (row caps, SQL subset).
- Setup guidance for registering the MCP alongside the plugin (`claude mcp add dataverse …`); link the comparison doc.

**Done when:** the skills name the routing rules and the README recommends running both.

### Phase D — Positioning & polish

- README repositioning: lead with *"the Dataverse MCP lets agents talk to your data; PowerPlatform-Core lets agents ship your solution."*
- One-command bootstrap (PowerShell + bash) that checks/installs prerequisites (Python, .NET 8, `pac`), attacking the setup-friction gap vs. the hosted MCP.
- `upsert_data.py --dry-run`: diff the would-be write against the current row for keyed update/upsert, no mutation.

### Release criteria

Branch → PR → live verification of Phases A + B by the maintainer → version bump to 1.5.0 (all six manifests — hosts cache by version) → tag + release.

## Backlog (v1.6+)

- **NL-query round-trip** — `query_data.py --question "…"`: draft FetchXML from a question, validate against live metadata, execute with paging (closes the MCP ergonomics gap without the MCP).
- **Preflight tokens everywhere** — extend Phase B to all remaining mutating helpers.
- **`platform-administration` Phase 2/3** — safe admin writes (create environment, tenant settings, managed environments), then high-risk ops (env delete/reset/restore, DLP CRUD via the Power Platform API), behind the admin preflight. *(Gated on maintainer go-ahead.)*
- **Security-role user/team assignment** helper (completes the roles story).
- **Generated capability matrix** — derive `docs/capability-matrix.md` from the scripts/tool surface to kill doc drift.
- **E2E-test one more harness** — GitHub Copilot CLI is the strategic pick.
- **Watch item:** Microsoft's "Dataverse skills for coding agents" (preview June 2026) — same form factor as this plugin; reassess overlap quarterly and keep the moat where it doesn't reach (flows, plug-in registration, ribbon/form surgery, delivery preflights).

## Explicitly out of scope

- **Power BI / PBIX editing** — evaluated July 2026 and declined: separate toolchain (PBIP/TMDL/Fabric APIs), dedicated-capacity licensing gates, zero reuse of the Dataverse/`pac` stack. Would dilute the plugin's focus; belongs in a separate project if ever.
- **A hosted/zero-install variant** — structurally at odds with a repo-first tool; the answer is a boring local install (Phase D), not a service.
