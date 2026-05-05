output "cidrs" {
  description = "Sorted, deduplicated list of Databricks CIDRs for the requested cloud + regions."
  value       = local.cidrs

  precondition {
    condition     = length(local.cidrs) >= var.min_cidr_count
    error_message = "Resolved ${length(local.cidrs)} CIDRs (need at least ${var.min_cidr_count}). Refusing to proceed — applying an empty list could clear all your firewall rules and lock you out. Likely causes: (1) wrong region name (browse ${var.source_base_url}/), (2) feed temporarily empty, (3) source URL or file misconfigured. Set min_cidr_count = 0 if you intentionally want to allow empty."
  }

  precondition {
    condition     = alltrue([for c in local.cidrs : can(cidrhost(c, 0))])
    error_message = "Feed contained non-CIDR lines. Bad values: [${join(", ", [for c in local.cidrs : c if !can(cidrhost(c, 0))])}]. Verify source_base_url or source_files point at a CIDR-per-line text feed (not JSON or HTML)."
  }
}

output "cidr_count" {
  description = "Number of CIDRs resolved. Useful for guardrails (e.g. resource cap checks)."
  value       = length(local.cidrs)
}

output "source" {
  description = "Where CIDRs were actually read from — either the resolved URL pattern or local file paths."
  value       = local.use_local ? var.source_files : [for f in local.feed_files : "${var.source_base_url}/${f}"]
}
