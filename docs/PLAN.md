# Plan

Four weeks, about 2 hours a day. Each week ends with a demo.

## Before starting

- [ ] Check which Claude models Bedrock offers in commercial AWS and GovCloud; pin one.
- [ ] Check S3 Vectors and Comprehend PII detection availability in the target regions.
- [ ] Pick the real name (check GitHub and PyPI). Create the public repo.
- [ ] Check outside-work and IP terms in the employment agreement before going public.
- [ ] Choose a license.

## Week 1: foundation and redaction scoring

- [ ] README skeleton, license.
- [ ] AWS account: MFA, budget alarm, Terraform state backend.
- [ ] Get the data; write `DATA.md` with each license.
- [ ] Local redaction CLI using Presidio.
- [ ] Scoring harness against ai4privacy (recall, precision).
- [ ] Decision record: why Python, why Presidio first.
- **Demo:** "Redaction catches X% of personal data across N labeled records," plus the command that reproduces it.

## Week 2: the pipeline in AWS

- [ ] Terraform: raw bucket → redaction Lambda → clean bucket, plus quarantine bucket. KMS, least-privilege IAM.
- [ ] Add Comprehend and Claude-as-redactor to the harness. Write the comparison.
- **Demo:** upload a file; watch the redacted copy, quarantined items, and audit record appear.

## Week 3: retrieval and the agent

- [ ] Embed clean text into S3 Vectors.
- [ ] Claude on Bedrock answers with citations. Log caller, documents used, prompt hash, model, tokens.
- [ ] Attack tests: prompt injection, PII extraction.
- [ ] Optional: classification step (Haiku default, Jev as alternative) with a comparison.
- **Demo:** cited answer, audit trail, attacks failing.

## Week 4: polish and the story

- [ ] GitHub Actions via OIDC: `terraform plan` on PRs, eval gates that block merges.
- [ ] GovCloud variables and README section.
- [ ] README: architecture diagram, eval numbers, cost per 1,000 docs, destroy walkthrough.
- [ ] Load test; write `SCALE.md`.
- [ ] Finish `BUILDING_WITH_AGENTS.md`. Demo video, resume bullet, LinkedIn post.
- Stretch: MCP server exposing cited search.
