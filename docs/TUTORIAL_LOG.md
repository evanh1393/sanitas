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

## Week 1, lesson 2: first GitHub Actions workflow (`.github/workflows/terraform.yml`)

Started 2026-09-29.

**Goal:** every PR that touches `infra/` gets `terraform fmt -check` and `terraform validate` run automatically, with no AWS credentials.

**Pieces:** GitHub Actions (primary), Terraform.

**Where we are (2026-09-29):** steps 1–5 done; PR #1 (`ci/terraform-checks`) green. PR #1 green → red (deliberate misformat) → green, squash-merged as `2c6af35`. tflint merged as PR #2 (`44f3dc1`), green in CI. Lesson 2 complete. Next: lesson 3, branch protection on `main` (make `checks` required; deal with the `paths` filter vs required-check problem).

### Steps

- [x] 1. Workflow file + trigger (PRs touching `infra/`)
- [x] 2. Job: checkout + install Terraform
- [x] 3. `fmt -check`
- [x] 4. `init -backend=false` + `validate`
- [x] 5. Push a branch, open a PR, watch it run
- [x] 6. Break fmt on purpose, see red, fix, squash-merge
- [x] 8. tflint (agent-written; Evan said he's got Actions down)

### Decisions and why

- Trigger: `pull_request` with `paths` on `infra/**` and the workflow file itself, so non-Terraform PRs skip it and edits to the workflow test themselves. (Path filters vs required checks gets revisited at branch protection.)
- `permissions: contents: read`: least-privilege `GITHUB_TOKEN`. `id-token: write` gets added with OIDC.
- `runs-on: ubuntu-latest`: GitHub-hosted runners are Ubuntu, Windows or macOS only (no Fedora/RHEL; use `container:` or self-hosted for that). Fresh VM per job = reproducible. The OS that matters is the one inside the Docker image (Lambda base images = Amazon Linux 2023).
- `terraform_version: "1.15.x"`: matches `required_version`, no surprise minor upgrades.
- `terraform fmt -check -recursive infra`: non-zero exit fails the step → job → PR check. Covers future stacks automatically.
- `init -backend=false` then `validate` in `infra/bootstrap`: validate needs the provider schema (downloaded per the committed lock file) but not state, so no AWS creds needed. `validate` isn't recursive; a matrix over stacks comes when there's a second stack.
- tflint: repo-root `.tflint.hcl` with the `terraform` ruleset (`recommended` preset) and the `aws` ruleset (pinned 0.49.0). `tflint --init` downloads plugins (needs `GITHUB_TOKEN` to avoid GitHub API rate limits); `--recursive` lints every stack; `--config` is an absolute path so each stack uses the root config. Tested on a scratch file: flags `t9.huge` instance type (error), untyped and unused variables (warnings). Any issue fails the job.
- Squash merge: the PR's test/fix commits collapse into one commit on `main`.
- Actions pinned to major tags (`@v5`, `@v3`) for now; pin to commit SHAs in the week 2 security step.

### Commands run

```bash
git switch -c ci/terraform-checks
git add .github/workflows/terraform.yml docs/TUTORIAL_LOG.md
git commit -m "Add Terraform fmt and validate checks on PRs"
git push -u origin ci/terraform-checks
gh pr create --fill                 # PR #1
gh pr checks --watch                # checks: SUCCESS
# step 6: misalign budget_type in budget.tf, commit, push  -> checks: fail (fmt step)
terraform fmt -recursive infra && git commit -am "Fix formatting" && git push   # green
gh pr merge --squash --delete-branch
git switch main && git pull
```

### Gotchas / things I got wrong

- VS Code flags the workflow as invalid until it has a `jobs:` block. It's just incomplete, not broken.

### Interview talking points

- fmt = style, validate = internally consistent, tflint = valid for AWS and best practice (bad instance types, unused/untyped variables, deprecated syntax). None need credentials.
- Test the gate: make it fail on purpose before trusting a green check.
- `validate` = internal consistency against the provider schema; `plan` = compared against real AWS (needs creds/state). Checks without credentials first, credentialed checks later.
- `uses:` runs an action (someone else's repo at a tag); `run:` runs your shell command. Actions run with your token and later your cloud role, so pin them to SHAs: tags can be moved.
- Runner VM starts empty: `checkout` clones the PR commit, `setup-terraform` puts the CLI on PATH.
- `ubuntu-24.04-arm` exists: matters for building arm64 (Graviton) Lambda images natively, about 20% cheaper Lambda.

## Week 1, lesson 3: branch protection on `main`

Started 2026-09-29.

**Goal:** nothing reaches `main` except through a PR whose required checks pass.

**Pieces:** GitHub rulesets (the gate), GitHub Actions (the checks).

**Where we are (2026-09-29):** steps 1–4 done. Direct push to `main` rejected (GH013); PR #3 was `BLOCKED` while `checks` ran, then squash-merged through the gate as `ed34b11`. Lesson 3 complete. Next: Week 1 Python work (README skeleton, data + `DATA.md`, or the `ModelProvider` interface); pick one from `docs/PLAN.md`.

### Steps

- [x] 1. Make branch protection available (repo made public)
- [x] 2. Make `checks` run on every PR (paths filter trap; agent made the edit)
- [x] 3. Ruleset on `main`: require PR + `checks`
- [x] 4. Test it: direct push rejected, PR blocked until `checks` green

### Decisions and why

- Repo made public instead of paying for GitHub Pro ($4/month): rulesets and branch protection on private repos need Pro on a personal account (API returned 403). It was going public anyway, and public repos get unlimited Actions minutes. History checked first: no secrets (`terraform.tfvars` never committed). Now public: commit author email and AWS account ID (not a secret per AWS).
- Dropped the workflow's `paths` filter: a required check whose workflow is skipped never reports, so the PR waits on "Expected — waiting for status" forever. Running `checks` on every PR costs ~1 min of free public-repo minutes. The gate-job pattern (one always-on `ci-ok` job) comes when there's a second workflow.
- Ruleset (Settings → Rules → Rulesets → New branch ruleset), not classic branch protection: rulesets are the newer replacement. Name `main`, Active, empty bypass list (even the admin can't skip it), target `~DEFAULT_BRANCH`. Rules: restrict deletions, block force pushes, require PR (0 approvals: solo dev can't approve own PR), require status check `checks` from GitHub Actions (integration 15368). "Require branches up to date" left off (forces rebase before every merge; not worth it solo).
- Hole noted: a PR can edit the workflow and keep a job named `checks` that does nothing. Solo, the fix is that only Evan can merge and he reads the diff. With collaborators: CODEOWNERS on `.github/` + required review. Orgs can use required workflows from a locked repo.
- Later option: manage the ruleset in Terraform (`github_repository_ruleset`) instead of UI clicks.

### Commands run

```bash
gh api repos/evanh1393/sanitas/rulesets          # 403 on private free repo: "Upgrade to GitHub Pro or make this repository public"
gh repo edit --visibility public --accept-visibility-change-consequences
git switch -c ci/required-checks                 # drop paths filter
git add .github/workflows/terraform.yml docs/TUTORIAL_LOG.md
git commit -m "Run Terraform checks on every PR" && git push -u origin ci/required-checks
gh pr create --fill && gh pr checks --watch      # PR #3 green
# UI: Settings -> Rules -> Rulesets -> New ruleset -> New branch ruleset
gh api repos/evanh1393/sanitas/rulesets/24160450 # verify rules
git switch main && git commit --allow-empty -m "Test: direct push should be rejected"
git push origin main                             # GH013: must be a PR; "checks" expected
git reset --hard origin/main                     # drop the probe commit
gh pr checks 3 --watch && gh pr merge 3 --squash --delete-branch && git pull
```

### Gotchas / things I got wrong

- `git switch main` refused: uncommitted edits to `TUTORIAL_LOG.md` would be overwritten because the branch had already changed that file. Commit (or stash) first.
- "New ruleset" is a dropdown: branch ruleset (protect `main`) vs tag ruleset (protect release tags, Week 4).
- After the ruleset, even doc updates like this one go through a PR.

### Interview talking points

- The gate is only real once tested: direct push rejected with GH013, PR shown `BLOCKED` until the required check finished.
- Required checks + path filters: a skipped workflow never reports, so the PR hangs. Fix by always running, or by a single always-on gate job.
- Required check pinned to the GitHub Actions app, so a status posted by another tool with the same name doesn't count.
- CI config is code: whoever can change and merge the workflow controls the gate. Mitigate with review (CODEOWNERS), SHA-pinned actions, and org-level required workflows.

### Q&A from this session (Terraform state)

- `state.tf` only creates the state bucket and KMS key, once, in bootstrap. Every stack needs a `backend "s3"` block with its own `key`; that's what points Terraform at its state.
- `init` wires up the backend and downloads providers; `apply` writes state. Terraform loads only the `.tf` files in the current folder (not subfolders) = one stack.
- State = what this stack has applied, with real IDs/ARNs. Not unapplied code, not other stacks.
- Variables: declared in `variables.tf`, valued in gitignored `terraform.tfvars` (or `-var`, `TF_VAR_*`, `default`), used as `var.x`. Inputs, not AWS resources. CI will use `TF_VAR_*` from secrets.
- `data` blocks read existing things (never create). Upcoming: `aws_kms_alias` to find the project key, `aws_partition` and `aws_caller_identity` for GovCloud-safe ARNs.
- Without a remote backend: local state, invisible to CI (fresh VM would try to recreate everything), no locking, lost with the laptop, plaintext on disk.
- Lint checks never touch the bucket (`init -backend=false`). `plan` in Week 2 will, via OIDC with S3 read and KMS decrypt.
