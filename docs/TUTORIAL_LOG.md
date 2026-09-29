# Tutorial log

Running notes for the write-up: what was built, why, and what was learned. One section per lesson, filled in as we go.

## Week 1, lesson 1: budget alarm + Terraform state bucket (`infra/bootstrap/`)

Started 2026-09-29.

**Goal:** protect spend from day one, and give every later Terraform stack a remote, encrypted, versioned place to keep state.

**Pieces:** Terraform (primary), AWS Budgets, S3, KMS.

### Steps

- [x] 1. Provider pinned to the `sanitas` profile
- [x] 2. ~$20/month budget with actual and forecast email alerts
- [ ] 3. State bucket: versioning, KMS encryption, public access block
- [ ] 4. Migrate the bootstrap's own state into the bucket

### Decisions and why

- Bootstrap runs by hand from a laptop with a named profile, never from CI. It creates the thing CI's state depends on (chicken and egg).
- AWS provider pinned `~> 6.0` (got v6.66.0): minor updates OK, no surprise major upgrade. `.terraform.lock.hcl` is committed so CI gets the exact same provider build; `.terraform/` is gitignored.
- `sanitas` profile assumes `OrganizationAccountAccessRole` in account 551626544335 via the `tf` source profile.
- Budget: $20/month COST budget. Alert on ACTUAL > 80% ($16) and FORECASTED > 100%. Budgets are free; direct email subscribers need no confirmation (unlike SNS).
- Alert email is a variable in gitignored `terraform.tfvars`, not hardcoded, because the repo goes public. Marked `sensitive = true` so it's hidden in plan output (matters once plans get posted as PR comments).

### Commands run

```bash
aws sts get-caller-identity --profile sanitas   # confirm the right account before touching anything
cd infra/bootstrap && terraform init            # download provider, write lock file
terraform fmt -check -recursive                 # same check CI will run
terraform validate && terraform plan            # budget: 1 to add
terraform apply
aws budgets describe-budgets --account-id 551626544335 --profile sanitas   # verify
```

Console: switch role into 551626544335 (`OrganizationAccountAccessRole`), then Billing and Cost Management → Budgets.

### Gotchas / things I got wrong

- `time_period_end = 2087-06-15` in the budget plan is AWS's "no end date", not a bug.
- Forecast alerts need some billing history before they can fire.

### Interview talking points

- Why a separate bootstrap stack: the state backend can't store its own state until it exists, so it's created with local state first, then migrated in.
