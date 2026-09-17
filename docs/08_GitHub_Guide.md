# GitHub Guide — Branching, PRs, Issues

## 1. Branch model
```
main          ← stable, always demoable (protect: no direct pushes)
dev           ← integration branch (PRs land here first)
feature/*     ← one branch per story:  feature/kafka-producer
fix/*         ← bug fixes:            fix/bert-schema-mutation
docs/*        ← documentation only:   docs/srs-draft
```

```bash
git switch dev && git pull
git switch -c feature/live-feed
# ... work, commit ...
git push -u origin feature/live-feed   # then open a PR into dev
```

## 2. Commit convention
Format: `type: short imperative summary`

| Type | Use |
|---|---|
| feat | new feature (producer, endpoint, chart…) |
| fix | bug fix |
| docs | documentation |
| test | tests only |
| chore | infra/config/deps |

Examples:
```
feat: add VADER pandas UDF to streaming job
fix: dedupe comment ids before Postgres upsert
docs: add SRS functional requirements
```

## 3. Pull requests
- Target `dev` (release merges `dev → main`).
- Fill the PR template (`.github/PULL_REQUEST_TEMPLATE.md`): what, why, how tested.
- One review before merge; CI (Jenkins/Actions) green.
- Squash-merge small PRs; merge-commit for multi-commit features.

## 4. Issues
- Templates in `.github/ISSUE_TEMPLATE/` (bug report / feature-task).
- Link issues in PRs (`Closes #12`).
- Label by component: `producer`, `spark`, `api`, `frontend`, `infra`.

## 5. Suggested protections
- `main`: require PR, 1 approval, no force push.
- `dev`: require PR.

## 6. Repo hygiene
- `.gitignore` covers venvs, checkpoints, model caches, datasets, node_modules.
- No secrets in the repo — DB creds are documented demo defaults only.
- Tag milestones: `git tag -a v1.0-demo -m "first full demo"` then push tags.
