# Terraform Module — Databricks IP Ranges

A small, focused Terraform module that exposes Databricks CIDR ranges (per cloud, per region) as a sorted, deduplicated list. Wire the output into any TF resource you already write — managed prefix lists, IP groups, storage account network rules, Cloud SQL authorized networks, Cloud Armor policies, anything.

This module owns CIDR sourcing. It does **not** write target resources for you. That's deliberate — keeps the module ~50 lines, works with any provider version, and avoids carrying maintenance for N target types.

---

## Quickstart

```hcl
module "dbx_ips" {
  source  = "github.com/bhavink/databricksIPranges//terraform?ref=main"
  cloud   = "azure"
  regions = ["eastus"]
}

resource "azurerm_storage_account_network_rules" "data" {
  storage_account_id = azurerm_storage_account.data.id
  default_action     = "Deny"
  bypass             = ["AzureServices"]
  ip_rules           = module.dbx_ips.cidrs
}
```

> **Always pin `?ref=`** to a tag or commit SHA in production — see [Stability](#stability--pinning) below.

---

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `cloud` | string | _(required)_ | `aws`, `azure`, or `gcp` |
| `regions` | list(string) | `[]` | Region names. Empty = use all-cloud feed (broader, not recommended for production) |
| `source_base_url` | string | `https://bhavink.github.io/databricksIPranges/output` | Base URL serving the per-region `.txt` feeds. Override for forks or self-hosted mirrors |
| `source_files` | list(string) | `[]` | Local CIDR-per-line file paths. Non-empty = airgapped/vendored mode (no network) |
| `min_cidr_count` | number | `1` | Refuse to apply below this. Guards against feed-empty lockouts. Set `0` to disable |
| `verify_checksums` | bool | `true` | Fetch `SHA256SUMS` from `source_base_url` and verify each feed's hash against it. No-op in `source_files` mode |

## Outputs

| Name | Type | Description |
|---|---|---|
| `cidrs` | list(string) | Sorted, deduplicated CIDRs |
| `cidr_count` | number | `length(cidrs)` |
| `source` | list(string) | URLs or local file paths actually read |

---

## Examples

### AWS — Managed Prefix List (one region)

```hcl
module "dbx_ips" {
  source  = "github.com/bhavink/databricksIPranges//terraform?ref=main"
  cloud   = "aws"
  regions = ["us-east-1"]
}

resource "aws_ec2_managed_prefix_list" "databricks" {
  name           = "databricks-aws-us-east-1"
  address_family = "IPv4"
  max_entries    = 200

  dynamic "entry" {
    for_each = toset(module.dbx_ips.cidrs)
    content { cidr = entry.value }
  }
}
```

### Azure — IP Group + Storage Account (multi-region)

```hcl
module "dbx_ips" {
  source  = "github.com/bhavink/databricksIPranges//terraform?ref=main"
  cloud   = "azure"
  regions = ["eastus", "westus2"]
}

resource "azurerm_ip_group" "databricks" {
  name                = "databricks-ip-ranges"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.network.name
  cidrs               = module.dbx_ips.cidrs
}

resource "azurerm_storage_account_network_rules" "data" {
  storage_account_id = azurerm_storage_account.data.id
  default_action     = "Deny"
  bypass             = ["AzureServices"]
  ip_rules           = module.dbx_ips.cidrs # IP Groups can't be referenced here
}
```

### GCP — Cloud SQL authorized networks

```hcl
module "dbx_ips" {
  source  = "github.com/bhavink/databricksIPranges//terraform?ref=main"
  cloud   = "gcp"
  regions = ["us-central1"]
}

resource "google_sql_database_instance" "this" {
  name             = "..."
  database_version = "POSTGRES_16"
  settings {
    ip_configuration {
      dynamic "authorized_networks" {
        for_each = toset(module.dbx_ips.cidrs)
        content {
          name  = "databricks-${replace(authorized_networks.value, "/", "-")}"
          value = authorized_networks.value
        }
      }
    }
  }
}
```

### Airgapped — vendor the feed

Commit the per-region file into your own repo, point the module at the local path:

```hcl
module "dbx_ips" {
  source       = "github.com/bhavink/databricksIPranges//terraform?ref=main"
  cloud        = "azure"
  source_files = ["${path.module}/vendored/azure-eastus.txt"]
}
```

A periodic job in your repo (e.g. Renovate, a scheduled GH Action) updates the vendored file via PR. Your TF apply only sees changes when that PR merges.

---

## Stability — pinning

| Strategy | `source` | When CIDRs change |
|---|---|---|
| **Tag** _(recommended)_ | `?ref=v2026.05.05` | When you bump the tag |
| **Commit SHA** _(strictest)_ | `?ref=a1b2c3d` | When you bump the SHA |
| **Branch** _(don't)_ | `?ref=main` | Every plan re-resolves — risk of unreviewed CIDR changes |

**Why pin:** Without it, every `terraform plan` re-resolves `main` and could surface CIDR diffs you haven't reviewed. Pinning makes the bump an explicit PR in your repo.

For the full threat model and recommended patterns by paranoia level (default → strict → airgapped/vendored), see [SECURITY.md](../SECURITY.md).

---

## Debugging

The module emits diagnostic outputs every run:

```bash
terraform output cidr_count       # how many CIDRs landed
terraform output source           # URLs or file paths actually read
terraform output cidrs | head     # spot-check first few
```

### Common errors

| Error | Cause | Fix |
|---|---|---|
| `Failed to fetch ... — HTTP 404` | Wrong region name or wrong cloud | Check `<source_base_url>/` for valid feeds |
| `Resolved 0 CIDRs ... need at least 1` | Empty/missing feed, typo'd region | Verify region name; or set `min_cidr_count = 0` if intentional |
| `Feed contained non-CIDR lines` | URL serves HTML/JSON, not text | Verify `source_base_url` points at the `output/` directory, not the JSON endpoint |
| `cloud must be one of: aws, azure, gcp` | Typo on `cloud` input | Use lowercase, exact match |
| `regions must contain only lowercase letters, digits, and hyphens` | Region has spaces, uppercase, or other chars | Use the exact region name from `<source_base_url>/` |
| `SHA256 mismatch for ...` | Feed body's hash doesn't match `SHA256SUMS` entry. Possible tampering, possible stale manifest | Compare hashes manually (see [SECURITY.md](../SECURITY.md)). If your fork doesn't publish `SHA256SUMS`, set `verify_checksums = false` |
| `Failed to fetch SHA256SUMS at ...` | URL returns non-200 — fork without manifest, or temporarily down | Set `verify_checksums = false` if your source intentionally doesn't publish one |

### Deeper diagnostics

```bash
TF_LOG=DEBUG terraform plan
```

Use this only for provider-level issues (TLS errors, proxy/DNS, IPv6 routing). Most user-facing errors are caught by validation/precondition messages above.

---

## Testing

Local:

```bash
cd terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform test
```

CI runs the same on every PR touching `terraform/` — see `.github/workflows/terraform.yml`.

Coverage:

| Behaviour | Test file | Test |
|---|---|---|
| Single-file happy path | `module.tftest.hcl` | `happy_path_single_file` |
| Multi-file union | `module.tftest.hcl` | `multi_file_union` |
| Comment + blank line stripping | `module.tftest.hcl` | `strips_comments_and_blanks` |
| Deduplication | `module.tftest.hcl` | `deduplicates` |
| Cloud input validation | `module.tftest.hcl` | `rejects_invalid_cloud` |
| Region format validation | `module.tftest.hcl` | `rejects_invalid_region_format` |
| Lockout guard (`min_cidr_count`) | `module.tftest.hcl` | `rejects_below_min_cidr_count` |
| Lockout guard disabled | `module.tftest.hcl` | `min_cidr_count_zero_allows_empty` |
| Non-CIDR content detection | `module.tftest.hcl` | `rejects_non_cidr_content` |
| Hash matches → pass | `checksums.tftest.hcl` | `verify_passes_when_hash_matches` |
| Hash mismatch → fail | `checksums.tftest.hcl` | `verify_fails_on_hash_mismatch` |
| File not in manifest → fail | `checksums.tftest.hcl` | `verify_fails_when_file_missing_from_manifest` |
| `verify_checksums = false` skips fetch | `checksums.tftest.hcl` | `verify_disabled_skips_fetch` |
| Local mode silently skips verify | `checksums.tftest.hcl` | `verify_silently_skipped_in_local_mode` |
| Manifest with blanks/comments tolerated | `checksums.tftest.hcl` | `manifest_with_blank_and_comment_lines_is_tolerated` |

Parsing tests use local fixtures; checksum tests use `mock_provider` `override_data` — no network required either way, full suite runs in seconds.

---

## Validating locally

Three layers — pick what you need. All three exiting `0` proves the entire chain (publish → fetch → verify → parse → emit) works end-to-end.

### 1. Run the test suite (no network)

```bash
cd terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform test
# Expect: Success! 15 passed, 0 failed.
```

> Requires Terraform `>= 1.6` (for the `test` framework). On Homebrew macOS, `homebrew/core` only ships 1.5.7 — switch to `hashicorp/tap/terraform`, install `opentofu` (drop-in, Apache-2.0), or grab a binary directly from `releases.hashicorp.com`.

### 2. Manual integrity check against the live URL

Verifies the published `SHA256SUMS` matches the published feeds — independent of the TF module:

```bash
mkdir -p /tmp/dbx-verify && cd /tmp/dbx-verify
curl -sO https://bhavink.github.io/databricksIPranges/output/SHA256SUMS
curl -sO https://bhavink.github.io/databricksIPranges/output/azure-eastus.txt
curl -sO https://bhavink.github.io/databricksIPranges/output/aws-us-east-1.txt
shasum -a 256 -c SHA256SUMS --ignore-missing
# Expect: azure-eastus.txt: OK
#         aws-us-east-1.txt: OK
```

### 3. End-to-end smoke test — real `terraform plan` against the live URL

Exercises the full module flow (fetch SHA256SUMS → fetch feed → verify hash → parse → emit). Use this when adopting the module to confirm your environment can reach the source and verify integrity.

```bash
mkdir -p /tmp/dbx-smoke && cat > /tmp/dbx-smoke/main.tf <<'EOF'
terraform {
  required_version = ">= 1.6"
}

module "dbx_ips" {
  source  = "github.com/bhavink/databricksIPranges//terraform?ref=main"
  cloud   = "azure"
  regions = ["eastus"]
  # verify_checksums defaults to true — exercises the full path
}

output "cidr_count"        { value = module.dbx_ips.cidr_count }
output "first_three_cidrs" { value = slice(module.dbx_ips.cidrs, 0, 3) }
output "source"            { value = module.dbx_ips.source }
EOF

terraform -chdir=/tmp/dbx-smoke init
terraform -chdir=/tmp/dbx-smoke plan
```

A successful plan output looks like:

```
module.dbx_ips.data.http.checksums[0]: Read complete after 0s [id=...SHA256SUMS]
module.dbx_ips.data.http.feed["azure-eastus.txt"]: Read complete after 0s [id=...azure-eastus.txt]

Changes to Outputs:
  + cidr_count        = 144
  + first_three_cidrs = [
      + "128.203.118.160/28",
      + "128.203.119.128/25",
      + "128.203.119.16/28",
    ]
  + source            = ["https://bhavink.github.io/databricksIPranges/output/azure-eastus.txt"]
```

If you see this, every postcondition passed: HTTP 200 + hash matches manifest + every line is a valid CIDR + `cidr_count >= min_cidr_count`. The chain is sound.

### Bonus — prove tamper detection trips

To watch the fail-closed behaviour fire, point the module at a source that doesn't publish a CIDR feed:

```bash
sed -i '' 's|github.com/bhavink/databricksIPranges//terraform?ref=main|github.com/bhavink/databricksIPranges//terraform?ref=main"\n  source_base_url = "https://example.com|' /tmp/dbx-smoke/main.tf
terraform -chdir=/tmp/dbx-smoke plan
# Expect: clean failure with "Failed to fetch SHA256SUMS at https://example.com/SHA256SUMS — HTTP 404"
```

---

## What this module deliberately does NOT do

- **Write target resources for you.** You write `aws_ec2_managed_prefix_list`, `azurerm_storage_account_network_rules`, etc. — that's where provider-specific limits and quirks live (rule caps, IPv4-only constraints, naming rules). Examples above show the patterns.
- **Validate cloud-provider caps** (AWS prefix list 200 entries, Azure storage account 400 IPs, etc.). Your resource block is the right place to fail on those.
- **Filter inbound vs outbound.** The published feeds already combine both. Use `source_files` against `<cloud>-<region>-inbound.txt` / `-outbound.txt` from your own fork if you need split feeds.
- **Refresh CIDRs automatically.** Pin a ref. Bump it via PR when you want to update.

---

## Stability guarantees

- Inputs and outputs are stable. New optional inputs may be added; existing inputs and output shapes will not change without a major version bump.
- The published feed format is `<cidr>\n<cidr>\n` (one CIDR per line, optional `#` comments and blank lines tolerated). Changing this is a breaking change for any consumer, not just this module — it would not be done lightly.
- The module fails closed: empty feed, non-CIDR content, or fetch failure all halt the apply rather than silently emitting garbage downstream.
