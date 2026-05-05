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

| Behaviour | Test |
|---|---|
| Single-file happy path | `happy_path_single_file` |
| Multi-file union | `multi_file_union` |
| Comment + blank line stripping | `strips_comments_and_blanks` |
| Deduplication | `deduplicates` |
| Cloud input validation | `rejects_invalid_cloud` |
| Region format validation | `rejects_invalid_region_format` |
| Lockout guard (`min_cidr_count`) | `rejects_below_min_cidr_count` |
| Lockout guard disabled | `min_cidr_count_zero_allows_empty` |
| Non-CIDR content detection | `rejects_non_cidr_content` |

Tests use `source_files` against committed fixtures — no network required, runs in seconds.

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
