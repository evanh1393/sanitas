# Tutorial log

Running notes for the write-up: what was built, why, and what was learned. One section per lesson, filled in as we go.

## Week 1, lesson 1: budget alarm + Terraform state bucket (`infra/bootstrap/`)

Started 2026-09-29.

**Goal:** protect spend from day one, and give every later Terraform stack a remote, encrypted, versioned place to keep state.

**Pieces:** Terraform (primary), AWS Budgets, S3, KMS.

**Where we are (2026-09-29):** steps 1–3 applied; 7 resources in local state. Next: step 4, add a `backend "s3"` block pointing at `sanitas-tfstate-551626544335` (KMS key `alias/sanitas`, `use_lockfile = true`) and run `terraform init -migrate-state`. After that: tick the Week 1 budget/state task in `docs/PLAN.md`.

### Steps

- [x] 1. Provider pinned to the `sanitas` profile
- [x] 2. ~$20/month budget with actual and forecast email alerts
- [x] 3. State bucket: versioning, KMS encryption, public access block
- [ ] 4. Migrate the bootstrap's own state into the bucket

### Decisions and why

- Bootstrap runs by hand from a laptop with a named profile, never from CI. It creates the thing CI's state depends on (chicken and egg).
- AWS provider pinned `~> 6.0` (got v6.66.0): minor updates OK, no surprise major upgrade. `.terraform.lock.hcl` is committed so CI gets the exact same provider build; `.terraform/` is gitignored.
- `sanitas` profile assumes `OrganizationAccountAccessRole` in account 551626544335 via the `tf` source profile.
- Budget: $20/month COST budget. Alert on ACTUAL > 80% ($16) and FORECASTED > 100%. Budgets are free; direct email subscribers need no confirmation (unlike SNS).
- Alert email is a variable in gitignored `terraform.tfvars`, not hardcoded, because the repo goes public. Marked `sensitive = true` so it's hidden in plan output (matters once plans get posted as PR comments).
- KMS: one customer-managed key (`alias/sanitas`, ~$1/month) for the whole project instead of the free AWS-managed `aws/s3` key: we control the key policy and every use shows in CloudTrail. Later stacks look it up by alias. Yearly rotation on; 7-day deletion window (the minimum).
- State bucket `sanitas-tfstate-551626544335`: account ID in the name because bucket names are global. `prevent_destroy` so Terraform refuses to delete it.
- Bucket settings are separate resources (provider v4+ style): versioning (recover old state), SSE-KMS with the project key plus `bucket_key_enabled` (cuts KMS request costs), and all four public access block flags.

### Commands run

```bash
aws sts get-caller-identity --profile sanitas   # confirm the right account before touching anything
cd infra/bootstrap && terraform init            # download provider, write lock file
terraform fmt -check -recursive                 # same check CI will run
terraform validate && terraform plan            # budget: 1 to add
terraform apply
aws budgets describe-budgets --account-id 551626544335 --profile sanitas   # verify
terraform plan && terraform apply               # state bucket + KMS: 6 to add
terraform state list                            # 7 resources
```

Console: switch role into 551626544335 (`OrganizationAccountAccessRole`), then Billing and Cost Management → Budgets.

### Gotchas / things I got wrong

- `time_period_end = 2087-06-15` in the budget plan is AWS's "no end date", not a bug.
- Forecast alerts need some billing history before they can fire.
- Writing resources isn't applying them: check `terraform state list` to see what actually exists.

### Interview talking points

- Why a separate bootstrap stack: the state backend can't store its own state until it exists, so it's created with local state first, then migrated in.
