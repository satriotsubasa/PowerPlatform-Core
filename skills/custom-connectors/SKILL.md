---
name: custom-connectors
description: >
  Use for designing Power Platform custom connectors and integration wrappers — reviewing an
  OpenAPI/Swagger description, choosing the auth shape (API key, OAuth2, basic, none), taking an
  operation inventory, and deciding whether to expose an API as a direct custom connector or
  behind an Azure Function / API facade. Produces a connector name, auth approach, operation
  summaries, a recommended pattern, suggested environment variables, and solution-aware
  connection-reference guidance. Trigger this whenever the user mentions a custom connector,
  OpenAPI/Swagger for Power Platform, connecting a flow or app to an external/REST API, an
  integration wrapper or facade, or asks whether an Azure Function should sit in front of an
  integration — even if no helper is named. This is design-first, not a connector publisher.
---

# Custom Connectors and Integration Wrappers

This skill helps design how Power Platform talks to an external API: reviewing the API description, settling the authentication shape, inventorying operations, and — critically — recommending whether the integration should be a direct custom connector or sit behind an Azure Function / API facade. It is design-first. It produces a reviewed structure and recommendation; the actual connector publish or Azure delivery still needs its own implementation path. Keep the result solution-aware with explicit connection references and environment variables so it promotes cleanly across environments.

## When to use this

- Review an OpenAPI/Swagger document or a structured integration requirement for connector suitability.
- Recommend an auth approach and inventory the operations to expose.
- Decide direct custom connector vs Azure Function / API facade.
- Plan the environment variables and connection references the integration needs for ALM.

For the flow that will *call* the connector, use `power-automate-flows`. For server-side logic inside Dataverse, use `plugins-server-extensions`.

## Helpers

Helpers live in the plugin's `scripts/` directory at the plugin root, not inside this skill folder. Resolve the plugin root and invoke them:

- Claude Code: `python "$CLAUDE_PLUGIN_ROOT/scripts/design_custom_connector.py" --help`
- Codex: `python "$CODEX_PLUGIN_ROOT/scripts/design_custom_connector.py" --help` (also exposed as `$PLUGIN_ROOT`)
- Standalone / unsure: the `scripts/` folder sits beside this skill bundle; invoke by its path within the install.

| Helper | Use it to |
| --- | --- |
| `design_custom_connector.py` | Review an OpenAPI description or structured requirement and emit a connector name, auth approach, operation summaries, a recommended pattern (direct connector vs facade), suggested environment variables, and connection-reference guidance. |

## Workflow

1. **Inspect the source.** Read the OpenAPI/Swagger description or the structured integration requirement before deciding anything.
2. **Judge direct-connector fit.** A clean, REST-shaped, JSON API with standard auth is a good direct custom-connector candidate.
3. **Prefer a facade when the shape is hard.** If the integration involves binary payloads, heavy transformation, fan-out/orchestration, or non-REST behavior, recommend an Azure Function (or similar) facade first and expose *that* as the connector.
4. **Settle auth.** Recommend the auth approach (API key, OAuth2, basic, none) that matches the API and the platform's supported connector auth types.
5. **Keep it solution-aware.** Plan explicit connection references and environment variables so credentials are not hardcoded and the connector promotes across Dev → Test → Prod.
6. **Hand off delivery.** State clearly what still needs a separate implementation path: publishing the connector, or building and deploying the Azure facade.

## Safety and decision rules

- This helper recommends structure and pattern; it does not publish a connector or deploy an Azure resource. Do not describe a connector as "created" or "deployed" beyond the design output.
- Default to a facade for binary, transform-heavy, fan-out, or non-REST integrations rather than forcing an awkward direct connector.
- Never hardcode secrets, endpoints, or tenant-specific values into the connector definition — route them through environment variables and connection references.
- If any connector or Azure delivery step performs a live mutation in an environment, run the **mandatory live-mutation preflight from the `powerplatform-core` orchestrator** first and stop if any required field is missing.
- When the task depends on current supported connector auth types or CLI behavior, verify against official Microsoft documentation before assuming.

## References

- `references/custom-connectors.md` — OpenAPI-based connector design review, auth recommendations, the direct-vs-facade decision path, expected output, and the design-first limits of the helper.
