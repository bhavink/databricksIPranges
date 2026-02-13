# GitHub CLI (gh) commands – databricksIPranges

Assumes [gh](https://cli.github.com/) is installed and authenticated (`gh auth login`).

## Repo

```bash
# Clone (if needed)
gh repo clone bhavink/databricksIPranges
cd databricksIPranges

# Open repo in browser
gh repo view bhavink/databricksIPranges --web

# Open Actions in browser
gh run list --repo bhavink/databricksIPranges --limit 5
gh run view --repo bhavink/databricksIPranges --web
```

## Trigger workflow (test run)

```bash
# Trigger "Update IP ranges" workflow (workflow_dispatch)
gh workflow run "Update IP ranges" --repo bhavink/databricksIPranges

# Trigger and watch until done
gh workflow run "Update IP ranges" --repo bhavink/databricksIPranges
gh run watch --repo bhavink/databricksIPranges
```

## Inspect runs

```bash
# List recent workflow runs
gh run list --repo bhavink/databricksIPranges --limit 10

# List runs for a specific workflow
gh run list --workflow "update.yml" --repo bhavink/databricksIPranges --limit 5

# View latest run (summary)
gh run view --repo bhavink/databricksIPranges

# View a specific run by ID
gh run view <run-id> --repo bhavink/databricksIPranges

# View logs of latest run
gh run view --repo bhavink/databricksIPranges --log

# Open run in browser
gh run view --repo bhavink/databricksIPranges --web
```

## Comments

```bash
# Comment on a PR (from repo root or with --repo)
gh pr comment <PR-number> --body "Your message here"
gh pr comment 3 --body "LGTM, thanks!" --repo bhavink/databricksIPranges

# Comment on an issue
gh issue comment <issue-number> --body "Your message here"
gh issue comment 1 --body "Fixed in main." --repo bhavink/databricksIPranges

# Comment from a file (e.g. for long or markdown content)
gh pr comment 3 --body-file comment.md --repo bhavink/databricksIPranges
gh issue comment 1 --body-file reply.txt --repo bhavink/databricksIPranges

# List comments on a PR or issue
gh pr view <PR-number> --comments --repo bhavink/databricksIPranges
gh issue view <issue-number> --comments --repo bhavink/databricksIPranges
```

From repo root you can omit `--repo bhavink/databricksIPranges`.
