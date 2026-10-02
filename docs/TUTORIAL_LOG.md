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

- Nothing is copied from the laptop's venv into the image. `uv.lock` travels; `uv sync --frozen` inside the build downloads the same versions and hashes. Laptop, image and CI install identical dependencies.
- A venv is just a folder: installing = resolve, download a wheel (a zip), unpack into `site-packages`, write console scripts. Python imports from whatever is on `sys.path`.
- Lambda layers: every layer zip is extracted into `/opt` as-is; the Python runtime adds `/opt/python` (and `/opt/python/lib/python3.x/site-packages`) to `sys.path`. That's why the zip's top folder must be `python/`. `/opt/bin` → `PATH`, `/opt/lib` → `LD_LIBRARY_PATH`. The `tf-sample` layer worked because `requests` is pure Python; compiled wheels (spaCy) must match Lambda's OS/arch/Python, and layers cap at 250 MB unzipped. Container images (10 GB) avoid both.
- `docker images` (containerd store): DISK USAGE = unpacked + compressed on this machine; CONTENT SIZE = compressed layers (ECR push and storage).
- Anything a `RUN` writes stays in that layer forever, even if a later step deletes it. Keep caches and build junk out with cache mounts (or multi-stage builds).
- Layer cache rule: cached up to the first instruction whose inputs changed; that step and everything after it rebuild. `COPY . .` before `uv sync` means any code edit reinstalls every dependency.

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

## Week 1, lesson 4: Docker (containerize the Python project)

Started 2026-09-29.

**Goal:** one image that runs the redaction code and its tests, identical on the laptop, in CI and later in Lambda.

**Pieces:** Docker (primary), Python/uv (the thing inside the image).

**Where we are (2026-09-29):** steps 1–6 done and pushed on `lesson4/docker`: `en_core_web_lg` added as a locked URL dependency; uv cache mount keeps a 729 MB duplicate out of the image. Step 7 done (not yet committed): `echo ... | docker run --rm -i sanitas:dev` redacts name, phone, email, SSN. Step 8 in progress: pytest added as a dev dependency, `tests/test_redact.py` (2 tests) passes locally with `uv run pytest`. Merged to `main` as PR #5 (`61bf2d7`). Decided (after going back and forth): multi-stage Dockerfile with a `test` target. `base`/`test`/`runtime` stages written; `docker run --rm sanitas:test` → `2 passed`, exit 0. Red/green check done: broken assert → `1 failed`, exit 1; fixed → `2 passed`, exit 0, and only `COPY . .` onward rebuilt. Step 8 done, merged as PR #6 (`17c3049`). **Lesson 4 complete.** Next: lesson 5, GitHub Actions builds the image and runs `sanitas:test` on every PR (PLAN.md Week 1 CI items; also decide how the required `checks` gate covers non-`infra/` PRs, and the empty uv cache mount on runners).

### Steps

- [x] 1. Branch + minimal Python package with uv
- [x] 2. First Dockerfile + `.dockerignore` (hello world in a container; CLI logic deferred)
- [x] 3. Add Presidio deps; rebuild with the naive Dockerfile, note size and time
- [x] 4. Layer caching: deps layer before code layer
- [x] 5. spaCy model `en_core_web_lg` as a uv URL dependency
- [x] 6. uv cache mount: keep uv's download cache out of the image
- [x] 7. Real redaction CLI (Presidio, stdin → redacted stdout)
- [x] 8. Run tests inside the container (multi-stage `test` target)

### Decisions and why

- uv for Python packaging: one tool for the Python version, venv, dependencies and lock file. Fast, and the same `uv sync --frozen` works in the Dockerfile.
- `--package` (src layout, `src/sanitas/`): the project is installable and gets a `sanitas` console command (`[project.scripts]`), so the container runs a real command. The src layout means tests import the installed package, not stray working-tree files. Redaction code will live in `src/sanitas/redact/` instead of the top-level `redact/` shown in CLAUDE.md.
- Python 3.13 pinned (`.python-version`, `requires-python >=3.13`): matches the Lambda Python base image, and spaCy has solid prebuilt wheels for it. Laptop default is 3.14; uv downloads 3.13 for this project, so laptop and container use the same version.
- Base image `python:3.13-slim` for now (small Debian + Python). Lambda's base image (`public.ecr.aws/lambda/python`) has its own runtime entrypoint; switch in Week 2.
- uv copied in with `COPY --from=ghcr.io/astral-sh/uv:<version> /uv /bin/uv`: pulls only the binary from Astral's image, pinned.
- `uv sync --frozen --no-dev`: install exactly the lock file, fail rather than re-resolve, skip dev tools.
- `ENV PATH=/app/.venv/bin:$PATH` + exec-form `CMD ["sanitas"]`: run the console script directly, no `uv run` sync at startup, no shell wrapper (signals reach the process).
- `.dockerignore`: `.venv` (host venv, host paths, would break the image), `.git`, `infra` out of the build context.
- Presidio (`presidio-analyzer`, `presidio-anonymizer`) added with `uv add`: took the image from ~150 MB to 1.06 GB on disk (238 MB compressed). spaCy, numpy, thinc etc.; the English model is still to come.
- Layer order: `COPY pyproject.toml uv.lock` → `uv sync --no-install-project` (deps only, ~900 MB, changes only when deps change) → `COPY . .` → `uv sync` (installs just `sanitas`, 0.2s). Least-changing layers first; same pattern as `package.json` before `npm install`.
- spaCy model `en_core_web_lg` (Presidio's default, ~425 MB) over `sm`/`md`: recall matters more than precision, and Presidio's docs and benchmarks assume `lg`. `sm` vs `lg` gets measured once the scoring harness exists. `trf` rejected: pulls in PyTorch (GBs).
- Model added as a URL dependency (`en_core_web_lg @ https://github.com/explosion/spacy-models/releases/...-3.8.0-py3-none-any.whl`), not `python -m spacy download` in the Dockerfile: pinned with a hash in `uv.lock`, lands in the cached deps layer, same model on laptop, image and CI. Model 3.8.x must match spaCy 3.8.x; `py3-none-any` = pure data/Python, works on any platform.
- BuildKit cache mount (`RUN --mount=type=cache,target=/root/.cache/uv`) on both `uv sync` steps: uv's cache lives on the build host, never in a layer. Also makes rebuilds after a lock change download only what's new. `ENV UV_LINK_MODE=copy` because hardlinks can't cross from the mount into the image filesystem. Alternative `UV_NO_CACHE=1` also keeps it out but loses the rebuild speedup. On GitHub runners the mount starts empty each job (fresh VM); handle in lesson 6.
- CLI: `redact(text) -> str` (pure function, testable without stdin) + `main()` (stdin → stdout). `AnalyzerEngine` finds entities with confidence scores (the future human-review threshold); `AnonymizerEngine` replaces spans with `<ENTITY_TYPE>`. Engines created per call for now; in Lambda they move to module level so the model loads once per cold start.
- Tests run in a multi-stage Dockerfile `test` target (`base` → `test` / `runtime`), not with uv on the Actions runner. Tests exercise the same layers that ship; pytest stays out of the runtime image. CI logic still lives in Actions: the workflow just runs `docker build --target test` and `docker run`. Considered and rejected: `uv run pytest` on the runner (simpler, faster, but never tests the image).
- `uv.lock` committed: exact versions of every dependency, so the image and CI install the same things the laptop did.

### Commands run

```bash
git switch -c lesson4/docker
uv init --package --name sanitas --python 3.13   # from repo root; keeps existing README.md
uv run sanitas                                   # downloads CPython 3.13, creates .venv, writes uv.lock -> "Hello from sanitas!"
docker build -t sanitas:dev .
docker run --rm sanitas:dev                      # "Hello from sanitas!"
uv add presidio-analyzer presidio-anonymizer     # updates pyproject.toml + uv.lock
docker images sanitas                            # 1.06GB disk, 238MB content
docker history sanitas:dev                       # size per layer
docker build --progress=plain -t sanitas:dev . 2>&1 | grep -E "CACHED|DONE|RUN|COPY"   # which steps hit cache
uv add "en_core_web_lg @ https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl"
docker images sanitas                            # 2.76GB disk, 1.05GB content: too big
docker run --rm sanitas:dev du -sh /root/.cache/uv /app/.venv   # 729M + 729M: uv cache baked into the image
# add cache mount, rebuild
echo "Call Maria Lopez at 212-555-0198 or maria.lopez@example.com. SSN 536-22-8134." \
  | docker run --rm -i sanitas:dev              # Call <PERSON> at <PHONE_NUMBER> or <EMAIL_ADDRESS>. SSN <US_SSN>.
docker run --rm sanitas:dev du -sh /root/.cache/uv /app/.venv   # cache: no such file; venv 729M
docker build --target test -t sanitas:test .   # builds base + test, skips runtime
docker run --rm sanitas:test; echo "exit: $?"   # 2 passed, exit: 0
```

### Gotchas / things I got wrong

- Dockerfile pinned uv `0.12.9` instead of `0.12.19` (typo). Still built, since the build backend (`uv_build`) is fetched separately, but the container's uv should match the one that wrote the lock.
- `uv run` creates `.venv/` and `uv.lock` on first use.
- `.dockerignore` patterns are root-relative: `__pycache__` only matches `./__pycache__`; use `**/__pycache__`. (`.gitignore` matches bare names at any depth.)
- `--no-cache` rebuilds your steps but doesn't re-pull base images (`--pull` does) and doesn't clear the uv cache mount.
- Image was 1.8 GB bigger than expected: `uv sync` in a plain `RUN` writes its download cache to `/root/.cache/uv`, which gets saved into the layer. Found by `du` inside the container (`docker run <image> <cmd>` overrides `CMD`).
- Agent mistake: said `docker images` DISK USAGE = unpacked image. With the containerd image store it's unpacked + compressed content (2.76 GB ≈ 1.7 GB unpacked + 1.05 GB compressed). CONTENT SIZE ≈ what's pushed to ECR; `du` inside the container = unpacked. `.venv/` is already gitignored; `uv.lock` gets committed.

### Interview talking points

## Week 1, lesson 5: GitHub Actions builds the image and runs the tests

Started 2026-09-29.

**Goal:** every PR builds the `test` target and runs pytest inside it, so a PR that breaks the image or the tests can't merge.

**Pieces:** GitHub Actions (primary), Docker (the same `docker build --target test` as on the laptop).

**Where we are (2026-09-29):** all steps done on PR #7 (`lesson5/ci-docker-tests`). `docker / test` green (28 s); red/green verified (broken assert → `1 failed`, exit 1, `terraform / checks` still green); layer cache skipped after measuring; `test` added to the `main` ruleset, and the red PR went `UNSTABLE` → `BLOCKED`, then `CLEAN` after the fix. **Lesson 5 complete once PR #7 merges.** Next: pick from PLAN.md Week 1 (lint step with ruff, `ModelProvider` interface, data + `DATA.md`, or the scoring harness).

### Steps

- [x] 1. `docker.yml`: build `--target test`, run it, on every PR
- [x] 2. Red/green: deliberately failing test turns the PR red
- [x] 3. Layer cache between runs: skipped (decided from the 28 s measurement)
- [x] 4. Add `test` to the `main` ruleset as a required check

### Decisions and why

- Separate workflow file (`docker.yml`) instead of a second job in `terraform.yml`: one concern per file; checks list shows `docker / test` next to `terraform / checks`. The job name `test` is what the ruleset will require.
- No `paths` filter: a required check that gets skipped leaves the PR stuck (lesson 3).
- `docker run` exit code = pytest exit code = step result; no extra wiring to fail the job.
- No layer cache (buildx `type=gha`) for now: the uncached job takes 28 s, and saving/restoring a ~1.7 GB layer likely costs more than it saves. Revisit in week 2 when CI pushes to ECR (a registry cache is an option then).

### Commands run

```bash
gh pr create --fill
gh pr checks --watch
gh run view <run-id> --log | grep -E "DONE|Installed|passed"   # per-step build timings
gh run view --log-failed                        # only the failing step's log
gh pr view 7 --json mergeStateStatus -q .mergeStateStatus   # UNSTABLE -> BLOCKED -> CLEAN
# UI: https://github.com/evanh1393/sanitas/settings/rules/24160450 -> Require status checks -> Add checks -> test
gh api repos/evanh1393/sanitas/rulesets/24160450 --jq '.rules[] | select(.type=="required_status_checks") | .parameters.required_status_checks'
```

### Gotchas / things I got wrong

- `gh pr checks` right after `git push` says "no checks reported": the new runs aren't queued yet. Wait a few seconds.
- Pushing is what triggers the PR checks; an uncommitted change doesn't run anywhere.
- Merge states: `UNSTABLE` = a non-required check failed, merge still allowed; `BLOCKED` = a required check failed or is missing; `CLEAN` = all good.
- Required check name = job name (`test`), not workflow name (`docker`). `integration_id` 15368 = GitHub Actions, so only an Actions job named `test` satisfies it.
- Agent mistake: said to edit the ruleset at Settings → Rules → Rulesets → `main`; the page Evan saw only offered "New ruleset". Direct edit URL works: `/settings/rules/<id>` (ID from `gh api repos/<owner>/<repo>/rulesets`).
- Agent mistake: predicted the uncached CI build would be slow (~1 GB download every run) and planned a layer cache to fix it. Measured: deps layer `uv sync` 11.1 s (56 packages, incl. the spaCy model), whole job 28 s. Runners have fast networks and uv is quick; a cache that saves/restores a ~1.7 GB layer probably wouldn't pay for itself.

### Interview talking points

- CI runs the same image target as the laptop; tests exercise the layers that ship.
- Measured before optimizing: uncached build is 28 s, so no layer cache yet.
- Proved the gate, not just the check: a red required check moves the PR from `UNSTABLE` (mergeable) to `BLOCKED`.

## Week 1, lesson 6: lint with ruff

Started 2026-09-29.

**Goal:** every PR fails if the Python code has lint errors or isn't formatted, using the same pinned ruff on the laptop and in CI.

**Pieces:** GitHub Actions (two new steps in the `test` job), Docker (ruff runs inside the `test` image; `.dockerignore` hardened), Python/uv (ruff as a dev dependency).

**Where we are (2026-09-29):** all steps done on PR #8 (`lesson6/ruff`). Red/green verified: unused import → `ruff check` failed (F401 + I001), `ruff format` skipped, PR `BLOCKED`; import removed → green (`test` 30 s). **Lesson 6 complete once PR #8 merges.** Next: pick from PLAN.md Week 1 (`ModelProvider` interface + `FakeProvider`, data + `DATA.md`, or the scoring harness).

### Steps

- [x] 1. `uv add --dev ruff`; `ruff check` + `ruff format --check` locally (clean)
- [x] 2. Two steps in `docker.yml`: `docker run --rm sanitas:test ruff check .` and `ruff format --check .`
- [x] 3. Red/green: unused import turns the PR red and `BLOCKED`

### Decisions and why

- Ruff runs inside the test image, not on the runner: the `test` target already installs the dev group, so ruff comes at the `uv.lock` version with no extra setup. Same reasoning as running pytest in the image (lesson 4). Rejected: separate `lint` job with `setup-uv` (faster feedback by ~20 s, but a second toolchain and another required check).
- Steps inside the existing `test` job, not a new job: already a required check, so no ruleset change. Cost: a test failure stops the job before lint runs.
- Two steps (`check`, `format`) instead of one: the log shows which one failed.
- Default ruff rules, no `[tool.ruff]` config yet. Ruff 0.16's defaults include import sorting (`I001`).
- `.dockerignore` now mirrors the private/local parts of `.gitignore`: `.env`, `.env.*`, `CLAUDE.local.md`, `.claude`, `.ruff_cache`, `data`. Build context dropped from 302 kB to under 1 kB.

### Commands run

```bash
uv add --dev ruff                                  # ruff 0.16.9 in the dev group
uv run ruff check .                                # lint
uv run ruff format --check .                       # formatting, no changes written
docker run --rm sanitas:test ruff check .          # same, inside the image (overrides CMD)
docker run --rm sanitas:test ls -a /app            # what COPY . . actually put in the image
gh run view <run-id> --json jobs --jq '.jobs[0].steps[]|"\(.name): \(.conclusion)"'   # per-step result
uv run ruff check --fix .                          # auto-fix rules marked [*]
```

### Gotchas / things I got wrong

- PR #7 wasn't actually merged before starting; `lesson6/ruff` was cut from the old `main` (no `docker.yml`). Fixed with `git stash` → merge → pull → recreate branch → `git stash pop`. Check `gh pr view <n> --json state` before branching.
- Squash commit for PR #7 got the branch name as its title. Use `gh pr create --title`.
- `.gitignore` doesn't apply to `docker build`. `COPY . .` had put the gitignored `CLAUDE.local.md` into local images (CI unaffected: the checkout has no gitignored files). Found because ruff counted 10 files in the container vs 9 on the laptop: with no `.git` in the image, ruff doesn't apply `.gitignore`.
- Adding a dev-only dependency changes `uv.lock`, which invalidates the deps layer (`COPY pyproject.toml uv.lock`) and re-exports the 1.7 GB layer (~14 s locally).
- `docker.yml` and `.dockerignore` lack a final newline.
- Agent mistake: said ruff's defaults were minimal and import sorting (`I`) could be added later. Ruff 0.16 already flags `I001` by default; the red/green run showed 2 errors, not the expected 1.

### Interview talking points

- Lint and tests run in the same image, so the ruff version is pinned by the lock file; no "works on my machine" linter drift.
- `.dockerignore` is a security control: the build context is everything not excluded, regardless of `.gitignore`. Verified by listing `/app` in the image.
- An unused import passes the tests but fails lint: why both gates exist.

## Week 1, lesson 7: labeled data + `DATA.md`

Started 2026-09-29.

**Goal:** a small, fixed, labeled sample committed to the repo, so the scoring harness (and later the CI eval gate) runs without network or credentials.

**Pieces:** Python/uv (sampling script), Docker (sample must be inside the build context), GitHub Actions (later: harness scores this file on every PR).

**Where we are (2026-09-29):** all steps done on PR #9 (`lesson7/data`): `eval/data/ai4privacy-en-200.jsonl` (200 English records, 1,696 labeled spans), `DATA.md` license + attribution. Ruff caught the sampling script locally before push (FURB122 + format); `checks` 20 s, `test` 31 s, both green. **Lesson 7 complete once PR #9 merges.** Next: lesson 8, scoring harness (recall/precision of `redact()` against the sample; first decision: map ai4privacy labels to Presidio entities, and span-overlap vs exact-match scoring).

### Steps

- [x] 1. Sampling script → `eval/data/ai4privacy-en-200.jsonl`
- [x] 2. `DATA.md`: source, license, attribution, how to regenerate
- [x] 3. Commit, PR, merge

### Decisions and why

- Dataset `ai4privacy/openpii-masking-mini-10k`: CC-BY-4.0, not gated. Other ai4privacy sets are "other"/custom licenses or gated commercial ones.
- 200-record committed JSONL sample (train split, `language == "en"`, `shuffle(seed=42)`), not a download at test time: reproducible, no network in CI, numbers can't drift if upstream changes. Kept only `uid`, `text`, `spans`.
- `uv run --with datasets`: one-off throwaway env; `datasets` (pyarrow, pandas) stays out of `uv.lock` and the image.
- Lives in `eval/data/`, not `data/`: `.dockerignore` excludes `data`, and the harness will run in the test image.

### Commands run

```bash
git switch -c lesson7/data
uv run --with datasets scripts/sample_ai4privacy.py
wc -l eval/data/ai4privacy-en-200.jsonl         # 200
```

### Gotchas / things I got wrong

- "Import could not be resolved" in the editor: `--with` deps live in a temporary env, not `.venv`. Harmless.
- Agent mistake: the sampling script as given failed ruff (FURB122 `f.write` in a loop; line over 88 chars). Caught by running `ruff check` + `ruff format --check` locally before pushing. VS Code now formats Python with ruff on save.
- Data is synthetic and mostly non-US formats (Canadian postal codes, 10-digit "social" numbers, `+7689036 9349` phones). Presidio's US recognizers (`US_SSN`) won't match many of these: expect low recall on some labels for format reasons, not model reasons.

### Interview talking points

- CC-BY-4.0 allows redistribution with attribution: creator, source link, license link, and a note of changes. Committing a sample is redistribution, so `DATA.md` carries all four.
- A small committed sample makes the eval hermetic: CI scores it with no network, no credentials, and no upstream drift. Seeded sampling script = provenance.
- Run the CI gate locally first (`ruff check`, `ruff format --check`): seconds instead of a CI round-trip.

## Week 1, lesson 8: scoring harness

Started 2026-09-29.

**Goal:** one command prints redaction recall and precision against the 200-record sample; later the same command gates PRs in CI.

**Pieces:** Docker (harness runs in the `test` image), GitHub Actions (later: eval gate job). Python written by the agent at Evan's request: the code isn't what this project demonstrates.

**Where we are (2026-09-29):** all steps done on PR #10. `redaction eval` step in `docker.yml` runs `eval/score.py` in the `test` image; CI printed the same 69.1% / 90.1% as the laptop. Red/green skipped (floor failure verified locally: exit 1). Merged by the agent at Evan's request. **Lesson 8 complete.** Next: Week 2 DevOps, starting with the GitHub OIDC provider + deploy role in Terraform.

### Steps

- [x] 1. `detect()` + `eval/score.py` (agent-written)
- [x] 2. Run locally and in the `test` image; record baseline
- [x] 3. CI eval gate: fail the `test` job below the floors
- [x] 4. PR, merge (red/green skipped; failure path checked locally)

### Decisions and why

- Character coverage, not any-overlap: a half-redacted SSN is a leak, so partial catches score partially.
- Label-agnostic: the job is removal; a phone caught as the wrong type is still redacted. No ai4privacy → Presidio label mapping.
- Report recall (what leaked) and precision (how much was over-redacted), plus per-label recall worst-first.
- `@cache` on the `AnalyzerEngine`: spaCy model loads once per process, not per record (same pattern as Lambda cold start).
- Floors: recall 65%, precision 85% (Evan's pick; baseline 69.1% / 90.1%). Constants at the top of `score.py`; `sys.exit(msg)` → exit 1 → step fails → `test` fails → PR blocked. No ruleset change: `test` was already required.
- Eval runs as the last step of `test`: slowest step, so tests and lint give feedback first.
- Harness is a plain script in `eval/`, found by `Path(__file__)`, so it runs the same on the laptop and at `/app` in the container.

### Commands run

```bash
git switch -c lesson8/scoring
uv run python eval/score.py                              # recall 69.1%, precision 90.1%
docker build --target test -t sanitas:test .
docker run --rm sanitas:test python eval/score.py        # same numbers in the image
```

### Gotchas / things I got wrong

- Pushed the branch but saw no checks: both workflows trigger on `pull_request`, so nothing runs until the PR exists.
- Weakest labels at baseline: SEX 0%, ZIPCODE 5%, DRIVERLICENSENUM 7%, IDCARDNUM 8%, GENDER 8%, TITLE 19%. Mostly types Presidio has no recognizer for, or non-US formats.

### Interview talking points

- Eval gate = a test that fails the build on a metric, not on a bug. Same exit-code chain as pytest and ruff.
- Same image, same lock file, same data → identical numbers on laptop and CI; no tolerance for noise needed.
- Scope note (Evan, 2026-09-29): the app is a "jazzier hello world" with a Bedrock hook; the project is about CI/CD and DevOps.

## Week 2, lesson 9: GitHub OIDC → AWS (no stored keys)

Started 2026-09-29.

**Goal:** GitHub Actions gets short-lived AWS credentials for one role, only for runs from `evanh1393/sanitas`, with no access keys stored anywhere. Unlocks ECR push, `plan` on PRs, and gated `apply`.

**Pieces:** Terraform (provider + role, in `infra/bootstrap/`), GitHub Actions (`id-token: write` + `configure-aws-credentials`), Docker (later: this role pushes images to ECR).

**Where we are (2026-10-02):** done, merged as PR #11. Next: lesson 10, ECR push via OIDC.

### Steps

- [x] 1. `aws_iam_openid_connect_provider` for `token.actions.githubusercontent.com`
- [x] 2. IAM role with trust policy (repo + branch/environment conditions)
- [x] 3. Evan applies provider + role together from the laptop
- [x] 4. Workflow step assumes the role; `aws sts get-caller-identity` in CI

### Decisions and why

- Lives in `infra/bootstrap/`: same chicken-and-egg as the state bucket; CI can't create the login it uses, so it's applied once by hand.
- No `thumbprint_list`: AWS validates GitHub's cert itself; optional in provider v6. Older tutorials hardcode a thumbprint that went stale.
- Immutable `sub` (`repo:evanh1393@56936902/sanitas@1394147480:...`): the repo sends owner/repo IDs, not just names. IDs survive renames and stop a recreated same-name repo from passing the trust policy.
- `AWS_ROLE_ARN` / `AWS_REGION` are repo *variables*, not secrets: an ARN isn't sensitive, the trust policy is the gate.
- Role has no permissions policy yet: `get-caller-identity` needs none. Permissions get added per job as they're needed.
- `client_id_list = ["sts.amazonaws.com"]`: the audience `configure-aws-credentials` requests; tokens for other audiences are rejected.

### Commands run

```bash
aws login --profile default          # AWS_PROFILE=tf is set in the shell; tf -> credential_process -> default
aws configure set region us-east-1 --profile tf
aws iam list-open-id-connect-providers --profile sanitas   # empty
git switch -c lesson9/github-oidc
```

### Gotchas / things I got wrong

- Agent mistake: told Evan to `aws login --profile sanitas`, then `--profile tf`. Profile chain is `sanitas` (assume role) → `tf` (`credential_process`) → `default` (the actual `aws login` session). Only `default` can log in.
- `AWS_PROFILE=tf` in the shell makes a bare `aws login` target `tf`; use `--profile default`.
- `aws login` via Claude Code's `!` prompt failed on the region question (no TTY); setting the region on the profile first avoided the prompt.
- Console equivalent: IAM → Identity providers → Add provider → OpenID Connect. Don't click-create it: Terraform's apply would then fail on the duplicate.
- Agent mistake: gave the old name-only `sub` format (`repo:evanh1393/sanitas:pull_request`). This repo uses the immutable subject, so AssumeRoleWithWebIdentity was denied 12 times. Found with `gh api repos/{owner}/{repo}/actions/oidc/customization/sub`.
- "Not authorized to perform sts:AssumeRoleWithWebIdentity" = `sub` or `aud` mismatch almost every time. Compare the policy to the real claim format.
- `gh run rerun --failed <id>` retries after an AWS-side fix; no new commit needed.

### Interview talking points

- OIDC = authentication (who is calling); the role's policy = authorization (what it may do); tflint/checkov = is the code sensible. Three separate controls.
- A role is something you become, not a login. OIDC replaces a long-lived access key in GitHub Secrets with a per-run token that expires in minutes.
- Why CI deploys at all: reviewed, recorded, repeatable changes; bootstrap stays manual because it creates what the pipeline stands on.
- Log shows `AWS_ACCESS_KEY_ID: ***`: temporary keys exist for the run only, masked, and expire. Nothing stored in GitHub.

## Week 2, lesson 10: build and push to ECR via OIDC

Started 2026-10-02.

**Goal:** on merge to `main`, Actions builds the `runtime` image and pushes it to a private ECR repo, tagged with the commit SHA, using the lesson 9 OIDC role. No stored keys.

**Pieces:** Terraform (ECR repo, lifecycle policy, push policy on the role, in `infra/bootstrap/ecr.tf`), GitHub Actions (`amazon-ecr-login`, build + push job), Docker (`runtime` stage becomes the image Lambda will run).

**Where we are (2026-10-02):** done, merged as PR #12. `push` run on `main` pushed `sanitas:899e3f0…` (~560 MB) to ECR. Next: pick the next Week 2 item (`terraform plan` on PRs, or the redaction Lambda).

### Steps

- [x] 1. `aws_ecr_repository`: immutable tags, existing KMS key, scan on push
- [x] 2. `aws_ecr_lifecycle_policy`: keep the last 10 images
- [x] 3. Inline role policy: `GetAuthorizationToken` on `*`, push actions on the repo ARN only
- [x] 4. Evan applies (`plan -out=tfplan`, `apply tfplan`)
- [x] 5. Workflow: OIDC → `amazon-ecr-login` → build `runtime` → push `:<sha>` on push to `main`
- [x] 6. Merge, watch the run, see the image in ECR

### Decisions and why

- ECR repo lives in `infra/bootstrap/`: next to the role that pushes to it, so the policy references the ARN directly; CI can't apply stacks yet.
- `IMMUTABLE` tags: one SHA = one image forever; nobody can swap what a tag points to.
- Reuse the one KMS key (`aws_kms_key.sanitas`): $1/month per key; ECR creates its own grant, so pushers need no KMS permissions.
- No `force_delete`: `destroy` fails while images exist. Free guard against accidental deletion.
- Lifecycle keeps 10 images (`tagStatus = any`): storage near $0, room to roll back.
- `GetAuthorizationToken` needs `"*"` (registry-wide, no resource-level support); written reason in a comment. Push actions scoped to the repo ARN.
- Known tradeoff: the trust policy also admits `pull_request` runs, so a PR run could push. Workflow only pushes on `main`; a separate main-only role can come with the gated deploy.
- Added `terrashark` skill as a Terraform review checklist (line in `CLAUDE.md`).
- `AWS_ROLE_ARN` stays a hand-set repo variable (Settings → Secrets and variables → Actions → Variables), not a Terraform output. Evan's call: one repo, one role, the trust policy is the gate. Known cost: renaming or recreating the role means updating the variable by hand.

### Concepts Evan worked through

- Role policy (`aws_iam_role_policy`) = what the role may do; repo policy (`aws_ecr_repository_policy`) = who may touch the repo. We used the former.
- Token = authentication (`docker login`); per-call IAM check = authorization. Same split as OIDC.
- Build happens on the runner (the GitHub-hosted VM from `runs-on`); needs no AWS permissions. ECR only stores. AWS only enters at push.

### Gotchas / things I got wrong

- Evan's `ecr.tf` had the `aws_iam_policy_document` but not the `aws_iam_role_policy` that attaches it. Plan said 2 to add, not 3; nobody checked the count. tflint (`terraform_unused_declarations`) failed `checks` on the PR before any deploy.
- Agent mistake: asked for "3 to add" but never confirmed the number, and didn't run `aws iam list-role-policies` after apply. Now: verify with a read-only check after every apply.
- `git add` with repo-root paths fails from `infra/bootstrap/`; `cd` to root or use `git add -A`.
- `push.yml` only triggers on `main`, so it never shows in PR checks; `gh run watch` after merge.

### Interview talking points

- A `data` block only describes; only `resource` blocks change infrastructure. A policy document with no attachment does nothing, and a linter can catch it.
- "CI can build anything, but it can only publish to one repo."
- Changing `name` or `encryption_configuration` on an ECR repo forces replacement, which deletes the images. Get them right on the first apply.
