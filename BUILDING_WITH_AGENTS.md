# Building with agents

An honest log of how agents were directed on this project: what was delegated, where the agent was wrong, and what was caught.

Format: `YYYY-MM-DD — what was delegated — what happened — what I caught or changed (link to diff)`

## Log

- 2026-09-28 — Delegated the "Before starting" research (Bedrock models, S3 Vectors/Comprehend regions, name clashes) — agent found all three name candidates taken on PyPI, Haiku 4.5 not in GovCloud, Comprehend PII in us-gov-west-1 only; the agent defaulted to Claude-specific framing and suggested a local Jenkins demo — I refocused on CI/CD with a swappable model behind a provider layer, dropped Jenkins, and kept Haiku 4.5 over DeepSeek.
