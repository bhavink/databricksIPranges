locals {
  use_local = length(var.source_files) > 0

  feed_files = length(var.regions) > 0 ? [
    for r in var.regions : "${var.cloud}-${r}.txt"
    ] : [
    "${var.cloud}.txt"
  ]

  # Hash verification only meaningful in URL mode. In local mode the customer
  # controls the file bytes, so verifying against an upstream SHA256SUMS
  # would be confusing (different sources, different hashes).
  do_verify = var.verify_checksums && !local.use_local
}

data "http" "checksums" {
  count = local.do_verify ? 1 : 0
  url   = "${var.source_base_url}/SHA256SUMS"

  retry {
    attempts     = 3
    min_delay_ms = 500
  }

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Failed to fetch SHA256SUMS at ${self.url} — HTTP ${self.status_code}. If your source_base_url doesn't publish SHA256SUMS, set verify_checksums = false to disable hash verification."
    }
  }
}

locals {
  # Parse SHA256SUMS body (GNU format: "<64-hex>  <filename>") into a map
  # keyed by filename. Tolerant of blank lines and `#` comments.
  expected_hashes = local.do_verify ? {
    for line in split("\n", data.http.checksums[0].response_body) :
    regex("^[0-9a-f]{64}  (.+)$", trimspace(line))[0] => substr(trimspace(line), 0, 64)
    if can(regex("^[0-9a-f]{64}  ", trimspace(line)))
  } : {}
}

data "http" "feed" {
  for_each = local.use_local ? toset([]) : toset(local.feed_files)
  url      = "${var.source_base_url}/${each.value}"

  retry {
    attempts     = 3
    min_delay_ms = 500
  }

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Failed to fetch ${self.url} — HTTP ${self.status_code}. Common causes: (1) misspelled region name, (2) region has no published feed (per-region files are emitted only when ≥1 CIDR exists), (3) wrong source_base_url. Browse available feeds at ${var.source_base_url}/."
    }

    postcondition {
      # Either verification is off, or the file's hash matches the manifest.
      # Using lookup() with empty default makes a missing-from-manifest
      # condition fail with a clear message rather than a TF map-lookup error.
      condition     = !local.do_verify || sha256(self.response_body) == lookup(local.expected_hashes, replace(self.url, "${var.source_base_url}/", ""), "")
      error_message = "SHA256 mismatch for ${self.url}. Expected ${lookup(local.expected_hashes, replace(self.url, "${var.source_base_url}/", ""), "(filename not present in SHA256SUMS)")}, got ${sha256(self.response_body)}. Possible tampering — refusing to apply. Verify SHA256SUMS at ${var.source_base_url}/SHA256SUMS or pin to a known-good ?ref=<sha>. If your source intentionally doesn't publish SHA256SUMS, set verify_checksums = false."
    }
  }
}

data "local_file" "feed" {
  for_each = local.use_local ? toset(var.source_files) : toset([])
  filename = each.value
}

locals {
  raw_lines = local.use_local ? flatten([
    for f in data.local_file.feed : split("\n", f.content)
    ]) : flatten([
    for f in data.http.feed : split("\n", f.response_body)
  ])

  cidrs = sort(distinct([
    for line in local.raw_lines :
    trimspace(line)
    if trimspace(line) != "" && !startswith(trimspace(line), "#")
  ]))
}
