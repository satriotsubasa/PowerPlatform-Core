# Security Policy

PowerPlatform-Core runs locally, authenticates to Microsoft Dataverse, and performs live mutations against real environments. Please treat security reports seriously and privately.

## Reporting a vulnerability

Please do not open a public GitHub issue for a security vulnerability.

Use GitHub's private vulnerability reporting for this repository: the **Report a vulnerability** button under the **Security** tab. If that is not available, contact the maintainer privately rather than filing a public issue.

Include enough detail to reproduce, and redact any secrets, environment or tenant URLs, or customer data.

## In scope

- Any path where a secret could be logged or exposed. The tool reads secrets (client secret, certificate password) from environment variables and never accepts them as command-line arguments; a regression there is in scope.
- Anything that could cause an unintended live mutation, bypass the live-mutation preflight gate, or target the wrong environment.

## Supported versions

This is an early-stage project. Fixes land on the latest release; there is no long-term support branch yet.
