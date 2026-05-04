#!/usr/bin/env python3
"""
Tests for update_outputs.py — focused on per-region feed emission logic.
Stubs the network fetch and routes filesystem writes through a tempdir.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent

FIXTURE = {
    "timestampSeconds": 1234567890,
    "schemaVersion": "1.0",
    "prefixes": [
        {"platform": "aws", "region": "us-east-1", "service": "Databricks",
         "type": "inbound",  "ipv4Prefixes": ["3.237.73.224/28"], "ipv6Prefixes": []},
        {"platform": "aws", "region": "us-east-1", "service": "Databricks",
         "type": "outbound", "ipv4Prefixes": ["44.215.162.0/24"], "ipv6Prefixes": []},
        {"platform": "aws", "region": "us-west-2", "service": "Databricks",
         "type": "outbound", "ipv4Prefixes": ["52.41.0.0/24"], "ipv6Prefixes": []},
        # Empty region — should NOT produce a file (guarded by the ≥1 CIDR check)
        {"platform": "aws", "region": "ghost-region", "service": "Databricks",
         "type": "outbound", "ipv4Prefixes": [], "ipv6Prefixes": []},
        {"platform": "azure", "region": "eastus", "service": "Databricks",
         "type": "inbound",  "ipv4Prefixes": ["20.42.4.209/32"], "ipv6Prefixes": []},
        {"platform": "gcp", "region": "us-central1", "service": "Databricks",
         "type": "outbound", "ipv4Prefixes": ["34.33.0.0/24"], "ipv6Prefixes": []},
    ],
}


def _load_module(tmp_docs: Path):
    """Load update_outputs.py with DOCS/OUTPUT_DIR pointed at a tempdir."""
    spec = importlib.util.spec_from_file_location(
        "update_outputs", REPO_ROOT / "update_outputs.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DOCS = tmp_docs
    mod.OUTPUT_DIR = tmp_docs / "output"
    mod.JSON_HISTORY_DIR = tmp_docs / "json-history"
    return mod


class _FakeResponse:
    """Stand-in for urllib.request.urlopen() context manager."""
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def _run_main():
    """Run update_outputs.main() against the fixture in a tempdir; return OUTPUT_DIR."""
    tmp = Path(tempfile.mkdtemp())
    mod = _load_module(tmp)

    # Stub load_extract_module().load_ip_ranges to return our fixture, so the per-region
    # loop and the per-cloud loop both see the same data.
    real_load = mod.load_extract_module
    extract_mod = real_load()

    def fake_load_ip_ranges(source=None):
        # mimic the normalizer in extract-databricks-ips.py
        return {"prefixes": extract_mod._normalize_prefixes(FIXTURE)}

    with mock.patch.object(extract_mod, "load_ip_ranges", side_effect=fake_load_ip_ranges):
        with mock.patch.object(mod, "load_extract_module", return_value=extract_mod):
            # Stub the JSON-history fetch (uses urllib directly inside main())
            with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(FIXTURE)):
                mod.main()

    return mod.OUTPUT_DIR


def test_per_region_files_emitted_for_nonempty_regions():
    out = _run_main()
    files = {p.name for p in out.iterdir() if p.suffix == ".txt"}
    assert "aws-us-east-1.txt" in files
    assert "aws-us-west-2.txt" in files
    assert "azure-eastus.txt" in files
    assert "gcp-us-central1.txt" in files


def test_empty_region_skipped():
    """A region whose entries have no CIDRs must not produce a file."""
    out = _run_main()
    files = {p.name for p in out.iterdir()}
    assert "aws-ghost-region.txt" not in files


def test_per_region_file_contains_only_that_region_cidrs():
    out = _run_main()
    aws_us_east_1 = (out / "aws-us-east-1.txt").read_text().strip().splitlines()
    assert "3.237.73.224/28" in aws_us_east_1
    assert "44.215.162.0/24" in aws_us_east_1
    # CIDR from us-west-2 must not leak in
    assert "52.41.0.0/24" not in aws_us_east_1


def test_per_region_includes_inbound_and_outbound():
    """Per-region feed combines both directions (matches the per-cloud all-types file)."""
    out = _run_main()
    aws_us_east_1 = set((out / "aws-us-east-1.txt").read_text().strip().splitlines())
    # Fixture has both inbound and outbound for us-east-1; both must appear
    assert {"3.237.73.224/28", "44.215.162.0/24"} <= aws_us_east_1


def test_per_cloud_files_still_emitted():
    """Regression guard: the original per-cloud feeds must keep working."""
    out = _run_main()
    files = {p.name for p in out.iterdir()}
    for expected in ["aws.txt", "aws-inbound.txt", "aws-outbound.txt",
                     "azure.txt", "gcp.txt", "all.txt"]:
        assert expected in files


def test_output_index_lists_region_files():
    """The generated output/index.html must include per-region files."""
    out = _run_main()
    index_html = (out / "index.html").read_text()
    assert "aws-us-east-1.txt" in index_html
    assert "azure-eastus.txt" in index_html


if __name__ == "__main__":
    sys.exit(__import__("pytest").main([__file__, "-v"]))
