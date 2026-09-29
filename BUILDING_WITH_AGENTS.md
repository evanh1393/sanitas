# Building with agents

An honest log of building this project with an agent as tutor and researcher: what I asked for, where the agent was wrong, and what I caught.

Format: `YYYY-MM-DD — what I asked for — what happened — what I caught or changed (link to diff)`

## Log

- 2026-09-28 — Delegated the "Before starting" research (Bedrock models, S3 Vectors/Comprehend regions, name clashes) — agent found all three name candidates taken on PyPI, Haiku 4.5 not in GovCloud, Comprehend PII in us-gov-west-1 only; the agent defaulted to Claude-specific framing and suggested a local Jenkins demo — I refocused on CI/CD with a swappable model behind a provider layer, dropped Jenkins, and kept Haiku 4.5 over DeepSeek.
- 2026-09-28 — Delegated AWS account setup checks for the new Sanitas account — agent turned a comment about who owns the org's root into an unrequested lecture on employment-agreement IP risk and suggested moving to a personal account — I shut it down: this is company-approved R&D and the only real constraint is spend. Redirected the caution into the budget alarm.
