# Sanitas

Latin for "soundness", the root of "sanitize". Chosen 2026-09-28 after Airlock, Sluice and Kestrel were taken on PyPI.

## What this is

An open-source, one-command AWS deployment that safely feeds sensitive documents to an LLM:

1. Documents come in (S3).
2. Personal data is found and removed.
3. Low-confidence detections go to a human review queue, not straight through.
4. Clean text is indexed in a vector store.
5. A model on Bedrock (Claude Haiku 4.5 by default) answers questions with citations.
6. Every model call is written to an audit log.

All infrastructure is Terraform. The model is a swappable part: the showcase is the CI/CD, testing, and infrastructure around it.

**The main thing to learn is CI/CD with GitHub Actions.** When choosing how to do something, prefer the option that teaches more about pipelines: PR checks, OIDC deploys, gated applies, scans, eval gates. AI frameworks like LangChain are welcome but secondary. Pitch: "I can put AI inside a locked-down environment and prove it doesn't leak."

## Who does what

Evan writes most of the code himself; it's how he learns. The agent works as a tutor:

- Walk through the work one small step at a time, with a brief "why" per line, then wait for Evan to say go.
- Give boilerplate, snippets and tips when asked. Don't write or edit code in the repo unless Evan asks for that specific piece.
- Research, read-only AWS checks, and upkeep of `docs/PLAN.md` are fine to do directly.

Evan also owns the things an agent can't decide:

- **What "good" means.** Metrics and thresholds, including the confidence level that routes to a human. Recall on personal data matters more than precision: a missed SSN is worse than an over-cleaned sentence.
- **The threat model**, written in plain language before the attack tests.
- **Decision records** in `docs/decisions/`, in Evan's own words. Draft options and tradeoffs if asked, but do not write the decision itself.
- **Deploys.** Evan runs `terraform apply`, or approves it in the gated GitHub Actions environment, and fixes deploy failures himself. The agent never runs `apply` or `destroy`.

Rule: nothing gets merged that Evan can't explain in an interview. Explain the why behind each step, briefly.

## Non-negotiables

These are the point of the project. Protect them.

1. **Numbers, not claims.** An eval suite measures recall/precision of redaction against labeled data, and whether answers are backed by their citations. CI fails if scores drop.
2. **Detector comparison.** Presidio, AWS Comprehend, and LLM-as-redactor (via Bedrock) run against the same labeled set.
3. **Attack tests.** Hidden prompt injection in documents, and questions that try to extract personal data. These run as tests.
4. **GovCloud-ready.** ARNs, endpoints, partitions, and model IDs come from variables. Never hardcode `arn:aws:`; use the partition.
5. **Security details.** No long-lived keys (GitHub Actions uses OIDC). KMS on every bucket. Least-privilege IAM per Lambda: no `*` actions or resources without a written reason. Budget alarm from day one.
6. **Human in the loop.** Low-confidence detections go to quarantine/review.
7. **`BUILDING_WITH_AGENTS.md`** is an honest log. When Evan catches a mistake of yours, it goes there.

## Cost rules

Target: under ~$20/month, close to $0 idle.

- Serverless only: S3, Lambda, SQS, DynamoDB on-demand, S3 Vectors, Bedrock per token.
- **Never add without asking:** NAT gateways, OpenSearch clusters, RDS, anything always-on, or more than one KMS key.
- Private networking (VPC + endpoints) sits behind `enable_private_networking = false`.
- Bulk load tests use Presidio, not an LLM.
- CI never calls Bedrock except the eval job. Unit and integration tests use the fake provider.

## Data and boundaries

- Public data and synthetic data only: ai4privacy (Hugging Face), Faker-generated records, Enron corpus, CFPB complaint narratives. Licenses recorded in `DATA.md`.
- Nothing from Evan's work: no data, code, names, or internal designs from any employer or client.
- No secrets in the repo. Local keys live in `.env` (gitignored); deployed keys live in Secrets Manager or SSM.
- Only already-redacted text may be sent to third-party (non-AWS) APIs.

## Stack

- Python for the pipeline and eval harness.
- Terraform for all infrastructure. Commercial AWS region for deploys.
- Models via Amazon Bedrock's Converse API, behind a `ModelProvider` interface. The model ID is config, never hardcoded. Dev default: Claude Haiku 4.5 (commercial only; not in GovCloud, where the docs name Sonnet 5). Embeddings: Titan Text Embeddings V2.
- Providers: `BedrockConverseProvider` for real runs, `FakeProvider` (canned responses) for tests.
- Docker: Lambdas ship as container images in ECR; the same image runs locally and in tests.
- CI/CD: GitHub Actions only (OIDC to AWS). No Jenkins.

## Layout (planned; create as needed)

```
redact/        local redaction CLI and detectors
eval/          scoring harness, labeled data loaders
pipeline/      Lambda handlers
infra/         Terraform
tests/         unit + attack tests
docs/          PLAN.md, decisions/, threat model
```

## Working rhythm

Sessions are ~2 hours. Start by reading `docs/PLAN.md` and picking one task. End by committing, adding a line to `BUILDING_WITH_AGENTS.md`, and ticking the task in `docs/PLAN.md`.
