# Plan

Four weeks, about 2 hours a day. Each week ends with a demo.

## Before starting

- [ ] Check which Claude models Bedrock offers in commercial AWS and GovCloud; pin one. (Chosen: Claude Haiku 4.5 for dev. Confirm the exact inference-profile ID with `aws bedrock list-inference-profiles`, then tick.)
- [x] Check S3 Vectors and Comprehend PII detection availability in the target regions. (S3 Vectors: GA, us-east-1/us-west-2 and both GovCloud regions. Comprehend PII: us-east-1/us-west-2 and us-gov-west-1 only.)
- [ ] Pick the real name (check GitHub and PyPI). Create the public repo.
- [ ] Check outside-work and IP terms in the employment agreement before going public.
- [ ] Choose a license.

## Week 1: foundation and redaction scoring

- [ ] README skeleton, license.
- [ ] AWS account: MFA, budget alarm, Terraform state backend.
- [ ] Get the data; write `DATA.md` with each license.
- [ ] `ModelProvider` interface: `BedrockConverseProvider` (real) and `FakeProvider` (tests). Model ID from config.
- [ ] Local redaction CLI using Presidio.
- [ ] Dockerfile for the redaction code; tests run inside the container.
- [ ] GitHub Actions: lint + unit tests (fake provider) on every PR.
- [ ] Scoring harness against ai4privacy (recall, precision).
- [ ] Decision record: why Python, why Presidio first.
- **Demo:** "Redaction catches X% of personal data across N labeled records," plus the command that reproduces it.

## Week 2: the pipeline in AWS

- [ ] Terraform: raw bucket → redaction Lambda → clean bucket, plus quarantine bucket. KMS, least-privilege IAM.
- [ ] Lambdas as container images in ECR (lifecycle policy to keep storage near $0).
- [ ] Add Comprehend and LLM-as-redactor (via the provider) to the harness. Write the comparison.
- **Demo:** upload a file; watch the redacted copy, quarantined items, and audit record appear.

## Week 3: retrieval and the agent

- [ ] Embed clean text into S3 Vectors.
- [ ] The model on Bedrock answers with citations. Log caller, documents used, prompt hash, model, tokens.
- [ ] Attack tests: prompt injection, PII extraction.
- [ ] Optional: classification step (Haiku default, Jev as alternative) with a comparison.
- **Demo:** cited answer, audit trail, attacks failing.

## Week 4: polish and the story

- [ ] GitHub Actions via OIDC: build and push images, `terraform plan` on PRs, eval gates (real model) that block merges.
- [ ] GovCloud variables and README section, including swapping the model ID (Haiku 4.5 is not in GovCloud).
- [ ] README: architecture diagram, eval numbers, cost per 1,000 docs, destroy walkthrough.
- [ ] Load test; write `SCALE.md`.
- [ ] Finish `BUILDING_WITH_AGENTS.md`. Demo video, resume bullet, LinkedIn post.
- Stretch: MCP server exposing cited search.
