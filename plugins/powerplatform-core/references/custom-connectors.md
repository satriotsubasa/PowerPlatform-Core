# Custom Connectors

Use this reference when the task is about custom connectors, OpenAPI review, or deciding whether to expose an integration directly or through a wrapper facade.

## Preferred Helper

- `scripts/design_custom_connector.py`

## Scope

- OpenAPI-based connector design review
- structured integration requirement review
- auth approach recommendations
- operation inventory
- environment-variable and connection-reference planning
- deciding when an Azure Function or similar facade is the safer shape

## Preferred Decision Path

1. Inspect the API description or structured requirement.
2. Decide whether the integration is a good direct custom-connector candidate.
3. If binary payloads, heavy transformation, fan-out, or non-REST behavior are involved, prefer a facade first.
4. Keep the connector solution-aware with explicit connection references and environment variables.

## Expected Output

- connector name
- auth approach
- operation summaries
- recommended pattern
- whether a facade is recommended
- suggested environment variables
- solution-aware connection-reference guidance

## Important Limits

- This helper is design-first, not a full connector publisher.
- It can recommend a facade and structure, but repo-specific Azure delivery still needs its own implementation path.
