// Unit tests for the databricksIPranges Terraform module.
// All tests use local source_files (no network) — covers the parsing logic,
// which is identical for URL and local file paths.
//
// Run: terraform -chdir=terraform test

run "happy_path_single_file" {
  command = plan

  variables {
    cloud        = "aws"
    source_files = ["tests/fixtures/region-a.txt"]
  }

  assert {
    condition     = length(output.cidrs) == 3
    error_message = "Expected 3 CIDRs from region-a fixture, got ${length(output.cidrs)}: ${jsonencode(output.cidrs)}"
  }

  assert {
    condition     = output.cidrs == sort(distinct(output.cidrs))
    error_message = "Output is not sorted+deduplicated."
  }

  assert {
    condition     = output.cidr_count == length(output.cidrs)
    error_message = "cidr_count must match length(cidrs)."
  }
}

run "multi_file_union" {
  command = plan

  variables {
    cloud        = "aws"
    source_files = ["tests/fixtures/region-a.txt", "tests/fixtures/region-b.txt"]
  }

  assert {
    condition     = length(output.cidrs) == 5
    error_message = "Expected union of region-a (3) + region-b (2) = 5 CIDRs, got ${length(output.cidrs)}."
  }

  assert {
    condition     = contains(output.cidrs, "3.237.73.224/28") && contains(output.cidrs, "52.41.0.0/24")
    error_message = "Union must contain CIDRs from both fixtures."
  }
}

run "strips_comments_and_blanks" {
  command = plan

  variables {
    cloud        = "aws"
    source_files = ["tests/fixtures/with-junk.txt"]
  }

  assert {
    condition     = length(output.cidrs) == 3
    error_message = "Expected 3 CIDRs after stripping comments/blanks, got ${length(output.cidrs)}: ${jsonencode(output.cidrs)}"
  }

  assert {
    condition     = length([for c in output.cidrs : c if startswith(c, "#") || c == ""]) == 0
    error_message = "Output must not contain blank or comment lines."
  }
}

run "deduplicates" {
  command = plan

  variables {
    cloud        = "aws"
    source_files = ["tests/fixtures/duplicates.txt"]
  }

  assert {
    condition     = length(output.cidrs) == 2
    error_message = "Expected 2 distinct CIDRs from duplicates fixture (5 lines, 2 unique), got ${length(output.cidrs)}."
  }
}

run "rejects_invalid_cloud" {
  command = plan

  variables {
    cloud        = "oracle"
    source_files = ["tests/fixtures/region-a.txt"]
  }

  expect_failures = [var.cloud]
}

run "rejects_invalid_region_format" {
  command = plan

  variables {
    cloud        = "aws"
    regions      = ["US East 1"]
    source_files = ["tests/fixtures/region-a.txt"]
  }

  expect_failures = [var.regions]
}

run "rejects_below_min_cidr_count" {
  command = plan

  variables {
    cloud          = "aws"
    source_files   = ["tests/fixtures/empty.txt"]
    min_cidr_count = 1
  }

  expect_failures = [output.cidrs]
}

run "min_cidr_count_zero_allows_empty" {
  command = plan

  variables {
    cloud          = "aws"
    source_files   = ["tests/fixtures/empty.txt"]
    min_cidr_count = 0
  }

  assert {
    condition     = length(output.cidrs) == 0
    error_message = "Empty fixture must produce zero CIDRs when min_cidr_count = 0."
  }
}

run "rejects_non_cidr_content" {
  command = plan

  variables {
    cloud        = "aws"
    source_files = ["tests/fixtures/non-cidr.txt"]
  }

  expect_failures = [output.cidrs]
}
