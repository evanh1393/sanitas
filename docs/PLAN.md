# Plan

Four weeks, about 2 hours a day. Each week ends with a demo.

CI/CD with GitHub Actions is the main thing to learn, so it grows every week instead of arriving at the end. Every change goes through a PR, and each week adds one more thing the pipeline does. By week 4, nothing reaches AWS except through the pipeline.

## Before starting

- [x] Check which Claude models Bedrock offers in commercial AWS and GovCloud; pin one. (Chosen: Claude Haiku 4.5 for dev, inference profile `us.anthropic.claude-haiku-4-5-20251001-v1:0`, ACTIVE in us-east-1 and us-west-2. The `us.` profile keeps requests in US regions; `global.` can route anywhere.)
- [x] Check S3 Vectors and Comprehend PII detection availability in the target regions. (S3 Vectors: GA, us-east-1/us-west-2 and both GovCloud regions. Comprehend PII: us-east-1/us-west-2 and us-gov-west-1 only.)
- [x] Pick the real name (check GitHub and PyPI). Create the public repo. (Sanitas. Repo `evanh1393/sanitas` exists, currently private.)
- [x] Choose a license. (MIT.)

## Week 1: foundation and redaction scoring

- [ ] README skeleton. (License done: MIT.)
- [x] AWS account: MFA, budget alarm, Terraform state backend. (Done 2026-09-29. MFA was already on the IAM user that assumes into the account.)
- [ ] Get the data; write `DATA.md` with each license.
- [ ] `ModelProvider` interface: `BedrockConverseProvider` (real) and `FakeProvider` (tests). Model ID from config.
- [x] Local redaction CLI using Presidio.
- [x] Dockerfile for the redaction code; tests run inside the container.
- [ ] Scoring harness against ai4privacy (recall, precision).
- [ ] Decision record: why Python, why Presidio first.
- CI/CD:
  - [ ] First workflow: lint + unit tests (fake provider) on every PR.
  - [ ] Build the Docker image in CI and run the tests inside it.
  - [x] Terraform checks in CI: `fmt -check`, `validate`, `tflint`. (Done 2026-09-29: PR #1 fmt + validate, PR #2 tflint with the AWS ruleset.)
  - [x] Branch protection on `main`: PRs only, required checks must pass. (Done 2026-09-29: repo made public for free rulesets; ruleset `main` requires a PR and `checks`, no bypass. PR #3 dropped the workflow's `paths` filter.)
- **Demo:** "Redaction catches X% of personal data across N labeled records," plus the command that reproduces it.

## Week 2: the pipeline in AWS

- [ ] Terraform: raw bucket → redaction Lambda → clean bucket, plus quarantine bucket. KMS, least-privilege IAM.
- [ ] Lambdas as container images in ECR (lifecycle policy to keep storage near $0).
- [ ] Add Comprehend and LLM-as-redactor (via the provider) to the harness. Write the comparison.
- CI/CD:
  - [ ] GitHub OIDC provider and deploy role in Terraform (no stored AWS keys).
  - [ ] Build and push images to ECR from Actions via OIDC.
  - [ ] `terraform plan` on every PR, posted as a PR comment.
  - [ ] `terraform apply` from Actions on merge, behind a GitHub environment that needs Evan's approval.
  - [ ] Security scans in CI: `checkov` (or `trivy config`) on Terraform, `trivy` on images.
- **Demo:** upload a file; watch the redacted copy, quarantined items, and audit record appear.

## Week 3: retrieval and the agent

- [ ] Embed clean text into S3 Vectors.
- [ ] The model on Bedrock answers with citations. Log caller, documents used, prompt hash, model, tokens.
- [ ] Attack tests: prompt injection, PII extraction.
- [ ] Optional: classification step (Haiku default, Jev as alternative) with a comparison.
- [ ] Optional: try LangChain (or similar) for the retrieval step behind the same provider interface; note what it adds or costs.
- CI/CD:
  - [ ] Attack tests as their own required CI job.
  - [ ] Integration tests against the container image with the fake provider.
  - [ ] Redaction eval gate: CI fails if recall or precision drops below the thresholds Evan sets.
- **Demo:** cited answer, audit trail, attacks failing, and a PR blocked by a failing check.

## Week 4: polish and the story

- CI/CD:
  - [ ] Eval job with the real model (the only CI job that calls Bedrock), gating merges.
  - [ ] Scheduled drift check: nightly `terraform plan` that alerts if AWS no longer matches the code.
  - [ ] Reusable workflows or composite actions to remove duplication.
  - [ ] Releases: tag, versioned image, changelog.
- [ ] GovCloud variables and README section, including swapping the model ID (Haiku 4.5 is not in GovCloud).
- [ ] README: architecture diagram, eval numbers, cost per 1,000 docs, destroy walkthrough.
- [ ] Load test; write `SCALE.md`.
- [ ] Finish `BUILDING_WITH_AGENTS.md`. Demo video, resume bullet, LinkedIn post.
- Stretch: MCP server exposing cited search.
