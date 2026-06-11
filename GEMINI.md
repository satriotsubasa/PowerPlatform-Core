# PowerPlatform-Core (Gemini CLI extension)

This extension loads the PowerPlatform-Core orchestrator skill, which discovers repo
context, routes to the right domain skill, and enforces the mandatory live-mutation
preflight. The orchestrator points to the domain skills under
`plugins/powerplatform-core/skills/`, which the agent reads as needed.

@./plugins/powerplatform-core/skills/powerplatform-core/SKILL.md
