// Mock-based tests for SHA256 verification logic. Uses override_data on the
// http data sources so we don't need network. The known hashes below were
// computed with: python3 -c 'import hashlib; print(hashlib.sha256(body).hexdigest())'

variables {
  cloud           = "aws"
  source_base_url = "https://example.test/output"
}

run "verify_passes_when_hash_matches" {
  command = plan

  variables {
    regions = ["alpha"]
  }

  override_data {
    target = data.http.checksums[0]
    values = {
      status_code   = 200
      response_body = "7179d5c23a29625799df8a2e0e6409b78ac6bf6ad09e0dabf5db6b92b7d581b2  aws-alpha.txt\n"
    }
  }

  override_data {
    target = data.http.feed["aws-alpha.txt"]
    values = {
      status_code   = 200
      response_body = "1.2.3.0/24\n"
      url           = "https://example.test/output/aws-alpha.txt"
    }
  }

  assert {
    condition     = length(output.cidrs) == 1 && output.cidrs[0] == "1.2.3.0/24"
    error_message = "Expected ['1.2.3.0/24'], got ${jsonencode(output.cidrs)}"
  }
}

run "verify_fails_on_hash_mismatch" {
  command = plan

  variables {
    regions = ["alpha"]
  }

  override_data {
    target = data.http.checksums[0]
    values = {
      status_code   = 200
      response_body = "0000000000000000000000000000000000000000000000000000000000000000  aws-alpha.txt\n"
    }
  }

  override_data {
    target = data.http.feed["aws-alpha.txt"]
    values = {
      status_code   = 200
      response_body = "1.2.3.0/24\n"
      url           = "https://example.test/output/aws-alpha.txt"
    }
  }

  expect_failures = [data.http.feed["aws-alpha.txt"]]
}

run "verify_fails_when_file_missing_from_manifest" {
  command = plan

  variables {
    regions = ["alpha"]
  }

  override_data {
    target = data.http.checksums[0]
    values = {
      status_code   = 200
      response_body = "deadbeef00000000000000000000000000000000000000000000000000000000  aws-other.txt\n"
    }
  }

  override_data {
    target = data.http.feed["aws-alpha.txt"]
    values = {
      status_code   = 200
      response_body = "1.2.3.0/24\n"
      url           = "https://example.test/output/aws-alpha.txt"
    }
  }

  expect_failures = [data.http.feed["aws-alpha.txt"]]
}

run "verify_disabled_skips_fetch" {
  command = plan

  variables {
    regions          = ["alpha"]
    verify_checksums = false
  }

  // No checksums data resource should be created when verify_checksums = false,
  // so we only override the feed.
  override_data {
    target = data.http.feed["aws-alpha.txt"]
    values = {
      status_code   = 200
      response_body = "1.2.3.0/24\n"
      url           = "https://example.test/output/aws-alpha.txt"
    }
  }

  assert {
    condition     = length(data.http.checksums) == 0
    error_message = "When verify_checksums = false, the checksums data resource must not be instantiated."
  }

  assert {
    condition     = length(output.cidrs) == 1 && output.cidrs[0] == "1.2.3.0/24"
    error_message = "Module must still produce CIDRs when verification is off."
  }
}

run "verify_silently_skipped_in_local_mode" {
  // verify_checksums defaults to true, but local mode (source_files set)
  // should suppress the SHA256SUMS fetch entirely.
  command = plan

  variables {
    source_files = ["tests/fixtures/region-a.txt"]
    // verify_checksums omitted — defaults to true
  }

  assert {
    condition     = length(data.http.checksums) == 0
    error_message = "Local mode must suppress the SHA256SUMS fetch even with verify_checksums = true (default)."
  }

  assert {
    condition     = length(output.cidrs) == 3
    error_message = "Local mode must still parse the local fixture."
  }
}

run "manifest_with_blank_and_comment_lines_is_tolerated" {
  command = plan

  variables {
    regions = ["alpha"]
  }

  override_data {
    target = data.http.checksums[0]
    values = {
      status_code   = 200
      response_body = <<-EOT
        # Manifest header — should be ignored

        7179d5c23a29625799df8a2e0e6409b78ac6bf6ad09e0dabf5db6b92b7d581b2  aws-alpha.txt

      EOT
    }
  }

  override_data {
    target = data.http.feed["aws-alpha.txt"]
    values = {
      status_code   = 200
      response_body = "1.2.3.0/24\n"
      url           = "https://example.test/output/aws-alpha.txt"
    }
  }

  assert {
    condition     = length(output.cidrs) == 1 && output.cidrs[0] == "1.2.3.0/24"
    error_message = "Manifest with blanks/comments must still verify and produce expected CIDRs."
  }
}
