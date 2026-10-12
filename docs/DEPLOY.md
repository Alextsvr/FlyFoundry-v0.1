# Deploying to GitHub (manual steps; the build session could not create the repository)

Blocked in the build session: `POST /user/repos` → HTTP 403 "sessions are bound to their configured repositories"; the session token is invalid.
From a machine where `gh` is authenticated:

```powershell
cd C:\Extra\flyfoundry
git init -b main   # skip if cloned from the bundle
gh repo create flyfoundry --public --source . --remote origin --push
gh workflow run experiment.yml -f generations=20 -f seeds=5 -f pop_size=100
gh run watch                       # wait for the run; then open the run summary and download artifact flyfoundry-report-<id>
gh api repos/{owner}/flyfoundry/branches/flyfoundry-state --jq .name   # state branch must now exist
gh workflow run experiment.yml -f generations=20                       # second run: log must say "restored checkpoint v1"
gh workflow list                   # experiment must be "active" (nightly schedule); GitHub disables schedules after 60 days without repo activity
```

Optional dashboard on GitHub Pages: Settings → Pages → Source "GitHub Actions", then repository variable `ENABLE_PAGES=true`.
Public repository is safe here because everything is synthetic; the state branch is public too.
Before the first push, double-check no secrets exist: `git grep -I -n -E "ghp_|github_pat_|BEGIN .*PRIVATE"` should print nothing.
