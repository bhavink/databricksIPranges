locals {
  use_local = length(var.source_files) > 0

  feed_files = length(var.regions) > 0 ? [
    for r in var.regions : "${var.cloud}-${r}.txt"
    ] : [
    "${var.cloud}.txt"
  ]
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
