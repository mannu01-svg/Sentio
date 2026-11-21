# GitHub Guide — Branching, PRs, Issues

## 1. Branch model
```
main          ← stable, always demoable (protect: no direct pushes)
feature/*     ← one branch per story:  feature/live-feed
fix/*         ← bug fixes:            fix/history-persistence
docs/*        ← documentation only:   docs/srs-final
```

```bash
git switch main && git pull
git switch -c feature/per-account-history
# ... work, commit ...
git push -u origin feature/per-account-history   # then open a PR into main
```

> The project used trunk-based development onto `main` (small student team,
> fast iterations) — the PR flow below still applied for every non-trivial
> change.

## 2. Commit convention
Format: `type: short imperative summary`

| Type | Use |
|---|---|
| feat | new feature (endpoint, tab, model, startup script…) |
| fix | bug fix (history persistence, keyword attribution…) |
| docs | documentation |
| test | tests only |
| chore | infra/config/deps/cleanup |

Real examples from this repo:
```
feat: one-command full setup per platform (app + services + zero-click Jenkins CI)
fix: history persistence + per-account attribution — history table auto-migration
chore: codebase cleanup — remove one-off scripts, stale logs, build artifacts
```

## 3. Pull requests
- Target `main`.
- Fill the PR template (`.github/PULL_REQUEST_TEMPLATE.md`): what, why, how tested.
- CI green (Jenkins `sentio-ci`) before merge.
- Squash-merge small PRs; merge-commit for multi-commit features.

## 4. Issues
- Templates in `.github/ISSUE_TEMPLATE/` (bug report / feature-task).
- Link issues in PRs (`Closes #12`).
- Label by component: `producer`, `spark`, `api`, `frontend`, `infra`, `docs`.

## 5. Large-file policy
- Fine-tuned weights: committed as **3 ≤90 MB parts + SHA256**
  (`models/sentiment-finetuned/model.safetensors.part00-02`) — rejoined by
  `split_weights.py --join` at setup. No LFS needed (GitHub's 100 MB hard
  limit respected; >50 MB triggers a warning, accepted).
- Datasets: bundled as plain CSVs (54 MB total, all < 40 MB per file).

## 6. Suggested protections
- `main`: require PR, 1 approval, no force push.

## 7. Repo hygiene
- `.gitignore` covers venvs, checkpoints, caches, logs, spark artifacts.
- Secrets live in `.env.local` (gitignored) — demo defaults documented in the README.
- Tag milestones: `git tag -a v1.0-midterm -m "mid-term demo"` /
  `v2.0-final` then push tags.
