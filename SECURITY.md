# Security Model

This repo publishes IP CIDR feeds that downstream consumers wire into firewalls. **Tampering with those feeds could open networks to attacker-controlled IPs or remove legitimate Databricks IPs and break workloads.** This document is the threat model and the recommended consumption patterns.

There is no perfect defense for any supply-chain dependency — you ultimately trust *some* publisher. The job is to make the trust boundary explicit, make tampering visible, and give you tools to verify before you apply.

## Trust boundary

When you consume from this repo, you are trusting:

1. The contents of the GitHub repo at the commit/tag you reference
2. Anyone with push access to that repo
3. The weekly GitHub Actions workflow that regenerates feeds
4. The upstream `https://www.databricks.com/networking/v1/ip-ranges.json` endpoint
5. GitHub itself (Pages, Actions, repo storage)

You can shrink this boundary substantially with a few patterns below.

## Highest-leverage defense: pin to a tag or commit SHA

This is the single most important thing. **Always pin `?ref=` to a tag or commit SHA in your Terraform module source, EDL URL, or wherever you reference these feeds.**

```hcl
# Recommended — tag pin (bumps weekly with publication)
module "dbx_ips" {
  source = "github.com/bhavink/databricksIPranges//terraform?ref=v2026.05.05"
  ...
}

# Strictest — commit SHA (you control exactly when CIDRs change)
module "dbx_ips" {
  source = "github.com/bhavink/databricksIPranges//terraform?ref=a1b2c3d"
  ...
}

# Don't — tracks main, every plan re-resolves, exposes you to unreviewed changes
module "dbx_ips" {
  source = "github.com/bhavink/databricksIPranges//terraform?ref=main"
  ...
}
```

Pinning means: a compromise of `main` does not automatically reach you. You only get new CIDRs when *you* explicitly bump the `?ref=` in your own repo, which goes through your own PR review.

## Defenses already in place (publish side)

This repo applies these by default:

| Defense | What it does |
|---|---|
| `SHA256SUMS` published with every release | Every `output/*.txt` file's hash is committed alongside the file. Consumers can verify before applying. |
| Weekly tagging (`v<YYYY.MM.DD>`) | Each publication gets an immutable tag. Pin to the tag. |
| GitHub Actions deps pinned by SHA | All third-party actions use commit SHA pins (not floating tags), preventing transitive action supply-chain attacks. |
| `permissions: contents: write` only | The weekly workflow has the minimum permissions needed; no secrets, no tokens beyond GITHUB_TOKEN. |
| Branch protection on `main` | Required PR review, no force push, no direct commits. |
| Reproducible publication | `update_outputs.py` is deterministic given the same `ip-ranges.json` snapshot. Anyone can re-run it and verify byte-identical output. |

## Recommended consumption patterns by paranoia level

### Default (most consumers)

- Pin `?ref=v<date>` to a recent tag in your TF module source
- Bump the tag periodically (monthly, or when notified of CIDR changes)
- Your `terraform plan` PR shows the CIDR diff — review before merging

This neutralizes most attacks because tampering between publications doesn't reach you.

### Stricter (regulated / high-stakes)

- Pin `?ref=<sha>` to a specific commit SHA
- Verify `SHA256SUMS` at fetch time (planned in PR 4 — TF module hash verification)
- Bump the SHA via a dedicated review PR with explicit security-team approval

### Most paranoid (airgapped / nation-state threat model)

- **Vendor the feeds into your own repo.** Commit `aws-us-east-1.txt` etc. directly to your IaC repo. TF reads via `data "local_file"`, no runtime dependency on this repo.
- A scheduled job (Renovate, scheduled GH Action) opens a "refresh CIDRs" PR with the new content, signed by your own automation. The diff is reviewed in your repo, by your team, before any apply.
- Removes us from the runtime trust chain entirely. Strongest possible answer.

```hcl
module "dbx_ips" {
  source       = "github.com/bhavink/databricksIPranges//terraform?ref=v2026.05.05"
  cloud        = "azure"
  source_files = ["${path.module}/vendored/azure-eastus.txt"]
}
```

## Verifying integrity manually

Every published `output/*.txt` is hashed in `output/SHA256SUMS`. To verify:

```bash
cd /tmp
curl -sO https://bhavink.github.io/databricksIPranges/output/SHA256SUMS
curl -sO https://bhavink.github.io/databricksIPranges/output/azure-eastus.txt
sha256sum -c SHA256SUMS --ignore-missing
# azure-eastus.txt: OK
```

If a file's hash doesn't match its `SHA256SUMS` entry, **do not use that file.** Open an issue.

## Reproducible build verification

The publication is deterministic. To verify a published file is what `update_outputs.py` would produce from a known-good `ip-ranges.json` snapshot:

```bash
git clone https://github.com/bhavink/databricksIPranges
cd databricksIPranges

# Pick a JSON snapshot from json-history/
SNAPSHOT=docs/json-history/ip-ranges-20260504-1712.json

# Run the extractor against that snapshot
python extract-databricks-ips.py --file "$SNAPSHOT" --cloud azure --region eastus > /tmp/expected.txt

# Compare against the published feed (or your fork's published feed)
diff /tmp/expected.txt docs/output/azure-eastus.txt
# (should be empty)
```

A divergence is provable evidence of tampering.

## What's deliberately out of scope

- **Compromise of GitHub itself, GitHub Pages, GitHub Actions infrastructure, or the Databricks publishing endpoint** — out of our control. Mitigated only by SHA pinning + vendoring (which use git's content-addressed storage).
- **Compromise of the upstream Databricks JSON URL** — if upstream is hijacked, this repo's feeds are also wrong. Detection: `validate_against_upstream` (planned, opt-in) cross-checks our published feed against the live Databricks JSON. Mitigation: pin to a known-good SHA from before the suspected compromise.
- **Solo-maintainer account compromise** — if my GitHub account is compromised, every defense above except reproducible-build verification breaks. The only real mitigation is an independent watchdog repo (out of scope for now).
- **Long-tail "stale fork goes bad"** — customers who don't review CIDR diffs before bumping `?ref=` can still consume a poisoned commit. The human gate (review the diff) is irreplaceable.

## Reporting a vulnerability

If you find a tampering pattern, a vulnerability in the publication pipeline, or a missing defense — **please do not open a public issue.** Email the maintainer directly (LinkedIn DM is fine if you don't have an email).

## Future work

- **PR 4 (planned):** TF module hash verification — fetch `SHA256SUMS` at plan time, compare against the hash of each fetched feed, fail the plan on mismatch. Defense-in-depth against single-file tampering between publications.
- **Optional:** SLSA provenance attestation via GitHub OIDC + Sigstore. Adds verifiable "this artifact was built from this workflow run on this commit." Not needed for v1.
- **Optional:** Independent watchdog repo on a separate identity that publishes the same files via the same logic. Defeats single-account compromise. Real defense, not yet implemented.
