# Tutorial log

Running notes for the write-up: what was built, why, and what was learned. One section per lesson, filled in as we go.

## Week 1, lesson 1: budget alarm + Terraform state bucket (`infra/bootstrap/`)

Started 2026-09-29.

**Goal:** protect spend from day one, and give every later Terraform stack a remote, encrypted, versioned place to keep state.

**Pieces:** Terraform (primary), AWS Budgets, S3, KMS.

**Where we are (2026-09-29):** steps 1–4 done; bootstrap state now lives in `s3://sanitas-tfstate-551626544335/bootstrap/terraform.tfstate`. Local leftovers deleted, committed (`91ca5bf`). MFA confirmed on; Week 1 account task ticked. Lesson 1 complete. Next: lesson 2, first GitHub Actions workflow (`terraform fmt -check` + `validate` on PRs touching `infra/`).

### Steps

- [x] 1. Provider pinned to the `sanitas` profile
- [x] 2. ~$20/month budget with actual and forecast email alerts
- [x] 3. State bucket: versioning, KMS encryption, public access block
- [x] 4. Migrate the bootstrap's own state into the bucket

### Decisions and why

- Bootstrap runs by hand from a laptop with a named profile, never from CI. It creates the thing CI's state depends on (chicken and egg).
- AWS provider pinned `~> 6.0` (got v6.66.0): minor updates OK, no surprise major upgrade. `.terraform.lock.hcl` is committed so CI gets the exact same provider build; `.terraform/` is gitignored.
- `sanitas` profile assumes `OrganizationAccountAccessRole` in account 551626544335 via the `tf` source profile.
- Budget: $20/month COST budget. Alert on ACTUAL > 80% ($16) and FORECASTED > 100%. Budgets are free; direct email subscribers need no confirmation (unlike SNS).
- Alert email is a variable in gitignored `terraform.tfvars`, not hardcoded, because the repo goes public. Marked `sensitive = true` so it's hidden in plan output (matters once plans get posted as PR comments).
- KMS: one customer-managed key (`alias/sanitas`, ~$1/month) for the whole project instead of the free AWS-managed `aws/s3` key: we control the key policy and every use shows in CloudTrail. Later stacks look it up by alias. Yearly rotation on; 7-day deletion window (the minimum).
- State bucket `sanitas-tfstate-551626544335`: account ID in the name because bucket names are global. `prevent_destroy` so Terraform refuses to delete it.
- Bucket settings are separate resources (provider v4+ style): versioning (recover old state), SSE-KMS with the project key plus `bucket_key_enabled` (cuts KMS request costs), and all four public access block flags.
- Backend `s3`, key `bootstrap/terraform.tfstate`; each later stack gets its own key in the same bucket. `kms_key_id = "alias/sanitas"` (explicit, so the backend can't override the bucket's KMS default; alias keeps `arn:aws:` out of code). `use_lockfile = true`: S3 lock file instead of the deprecated DynamoDB lock table.
- Backend values are literals: backend blocks can't use variables or reference resources (configured at `init`, before anything else is read). Later stacks can use partial backend config for GovCloud.

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
# step 4: add backend "s3" block, then
terraform init -migrate-state                   # answer "yes" to copy local state to S3
terraform state list && terraform plan          # same 7, "No changes"
aws s3api head-object --bucket sanitas-tfstate-551626544335 \
  --key bootstrap/terraform.tfstate --profile sanitas   # aws:kms, our key ID
```

Console: switch role into 551626544335 (`OrganizationAccountAccessRole`), then Billing and Cost Management → Budgets.

### Gotchas / things I got wrong

- `time_period_end = 2087-06-15` in the budget plan is AWS's "no end date", not a bug.
- Forecast alerts need some billing history before they can fire.
- Writing resources isn't applying them: check `terraform state list` to see what actually exists.
- After migration, local `terraform.tfstate` is 0 bytes (emptied on purpose) and `.tfstate.backup` is a plaintext copy of old state. `.terraform/terraform.tfstate` is different: a cache of backend settings, not resource state.
- `sensitive = true` hides values in output only; they're still plaintext in state. That's why the state bucket is encrypted and locked down.

### Interview talking points

- Why a separate bootstrap stack: the state backend can't store its own state until it exists, so it's created with local state first, then migrated in.
- State is Terraform's map from code to real resource IDs: a snapshot of what `apply` built, not a history (history = S3 versioning, git, CloudTrail).
- Remote state is what lets CI run Terraform: the backend puts state somewhere reachable; IAM (OIDC role with S3 + `kms:Decrypt`/`GenerateDataKey`) decides who can reach it.
- Human access: IAM user with MFA → `aws login` (short-lived creds) → assume `OrganizationAccountAccessRole`. No access keys anywhere.
- Locking: S3 `use_lockfile` now; S3 + DynamoDB is the older pattern you'll see in most codebases.
