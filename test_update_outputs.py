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


def test_per_region_direction_files_emitted_when_cidrs_exist():
    """For a region that has both inbound and outbound CIDRs, both direction-scoped
    files must be emitted alongside the combined one."""
    out = _run_main()
    files = {p.name for p in out.iterdir() if p.suffix == ".txt"}
    assert "aws-us-east-1-inbound.txt" in files
    assert "aws-us-east-1-outbound.txt" in files


def test_per_region_inbound_contains_only_inbound_cidrs():
    out = _run_main()
    inbound = set((out / "aws-us-east-1-inbound.txt").read_text().strip().splitlines())
    # Fixture us-east-1 inbound: 3.237.73.224/28; outbound: 44.215.162.0/24
    assert "3.237.73.224/28" in inbound
    assert "44.215.162.0/24" not in inbound


def test_per_region_outbound_contains_only_outbound_cidrs():
    out = _run_main()
    outbound = set((out / "aws-us-east-1-outbound.txt").read_text().strip().splitlines())
    assert "44.215.162.0/24" in outbound
    assert "3.237.73.224/28" not in outbound


def test_per_region_direction_skipped_when_no_cidrs():
    """us-west-2 fixture only has outbound — the -inbound.txt must NOT be emitted.
    Same ≥1-CIDR guard as the combined per-region file."""
    out = _run_main()
    files = {p.name for p in out.iterdir()}
    assert "aws-us-west-2-outbound.txt" in files  # has outbound CIDR
    assert "aws-us-west-2-inbound.txt" not in files  # has no inbound CIDR
    # ghost-region has neither direction with content — none of the three variants exist
    assert "aws-ghost-region.txt" not in files
    assert "aws-ghost-region-inbound.txt" not in files
    assert "aws-ghost-region-outbound.txt" not in files


def test_per_region_direction_files_covered_by_sha256sums():
    """Defense-in-depth: the new direction-scoped files must be in SHA256SUMS so
    consumers fetching them can verify integrity."""
    out = _run_main()
    sha_lines = (out / "SHA256SUMS").read_text().splitlines()
    sha_files = {line.split("  ", 1)[1] for line in sha_lines if "  " in line}
    assert "aws-us-east-1-inbound.txt" in sha_files
    assert "aws-us-east-1-outbound.txt" in sha_files


def test_output_index_lists_region_direction_files():
    """The generated output/index.html must include per-region+direction files
    so they're discoverable from the browser."""
    out = _run_main()
    index_html = (out / "index.html").read_text()
    assert "aws-us-east-1-outbound.txt" in index_html


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


def test_sha256sums_emitted():
    """SHA256SUMS file must be generated alongside the txt files."""
    out = _run_main()
    assert (out / "SHA256SUMS").is_file(), "SHA256SUMS file missing"


def test_sha256sums_format_is_gnu():
    """Every line: <64-hex-digest>SPSP<filename>. Compatible with `sha256sum -c`."""
    import re
    out = _run_main()
    content = (out / "SHA256SUMS").read_text()
    lines = [line for line in content.splitlines() if line.strip()]
    assert len(lines) > 0
    for line in lines:
        assert re.match(r"^[0-9a-f]{64}  \S+", line), f"Bad SHA256SUMS line: {line!r}"


def test_sha256sums_contents_are_correct():
    """For each line, the recorded digest must match the on-disk file's actual sha256."""
    import hashlib
    out = _run_main()
    content = (out / "SHA256SUMS").read_text()
    for line in content.splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        target = out / name
        assert target.is_file(), f"SHA256SUMS references missing file: {name}"
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual == digest, f"Digest mismatch for {name}: recorded={digest}, actual={actual}"


def test_sha256sums_does_not_include_self():
    """SHA256SUMS must not list itself (avoids chicken-and-egg verification)."""
    out = _run_main()
    content = (out / "SHA256SUMS").read_text()
    assert "SHA256SUMS" not in [line.split("  ", 1)[1] for line in content.splitlines() if "  " in line]


def test_sha256sums_covers_all_txt_files():
    """Every .txt file in output/ must have a SHA256SUMS entry."""
    out = _run_main()
    txt_files_on_disk = {p.name for p in out.iterdir() if p.suffix == ".txt"}
    sha_lines = (out / "SHA256SUMS").read_text().splitlines()
    sha_files = {line.split("  ", 1)[1] for line in sha_lines if "  " in line}
    missing = txt_files_on_disk - sha_files
    assert not missing, f"SHA256SUMS missing entries for: {missing}"


def test_output_index_links_sha256sums():
    """The directory index must link to SHA256SUMS so consumers can find it."""
    out = _run_main()
    index_html = (out / "index.html").read_text()
    assert "SHA256SUMS" in index_html


def test_history_snapshot_written_on_first_run():
    tmp = Path(tempfile.mkdtemp())
    mod = _load_module(tmp)
    extract_mod = mod.load_extract_module()

    def fake_load_ip_ranges(source=None):
        return {"prefixes": extract_mod._normalize_prefixes(FIXTURE)}

    with mock.patch.object(extract_mod, "load_ip_ranges", side_effect=fake_load_ip_ranges):
        with mock.patch.object(mod, "load_extract_module", return_value=extract_mod):
            with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(FIXTURE)):
                mod.main()

    history_files = list(mod.JSON_HISTORY_DIR.glob("ip-ranges-*.json"))
    assert len(history_files) == 1


def test_history_dedups_identical_content():
    """Running twice with unchanged upstream JSON must not create a second file —
    only the timestamp would differ, which isn't a meaningful change to record."""
    tmp = Path(tempfile.mkdtemp())
    mod = _load_module(tmp)
    extract_mod = mod.load_extract_module()

    def fake_load_ip_ranges(source=None):
        return {"prefixes": extract_mod._normalize_prefixes(FIXTURE)}

    with mock.patch.object(extract_mod, "load_ip_ranges", side_effect=fake_load_ip_ranges):
        with mock.patch.object(mod, "load_extract_module", return_value=extract_mod):
            with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(FIXTURE)):
                mod.main()
                mod.main()

    history_files = list(mod.JSON_HISTORY_DIR.glob("ip-ranges-*.json"))
    assert len(history_files) == 1


def test_history_writes_new_snapshot_on_content_change():
    """Two runs a week apart (distinct timestamps) with different upstream content
    must each get their own snapshot file."""
    import datetime as dt_module

    tmp = Path(tempfile.mkdtemp())
    mod = _load_module(tmp)
    extract_mod = mod.load_extract_module()

    def fake_load_ip_ranges(source=None):
        return {"prefixes": extract_mod._normalize_prefixes(FIXTURE)}

    changed_fixture = json.loads(json.dumps(FIXTURE))
    changed_fixture["prefixes"][0]["ipv4Prefixes"] = ["9.9.9.0/24"]

    class _FrozenDatetime(dt_module.datetime):
        _now = dt_module.datetime(2026, 1, 1, tzinfo=dt_module.timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls._now

    with mock.patch.object(extract_mod, "load_ip_ranges", side_effect=fake_load_ip_ranges):
        with mock.patch.object(mod, "load_extract_module", return_value=extract_mod):
            with mock.patch.object(mod, "datetime", _FrozenDatetime):
                with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(FIXTURE)):
                    mod.main()
                _FrozenDatetime._now = dt_module.datetime(2026, 1, 8, tzinfo=dt_module.timezone.utc)
                with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(changed_fixture)):
                    mod.main()

    history_files = list(mod.JSON_HISTORY_DIR.glob("ip-ranges-*.json"))
    assert len(history_files) == 2


def test_prune_history_removes_old_snapshots_but_keeps_newest():
    tmp = Path(tempfile.mkdtemp())
    mod = _load_module(tmp)
    mod.JSON_HISTORY_DIR.mkdir(parents=True)

    old = mod.JSON_HISTORY_DIR / "ip-ranges-20200101-0000.json"
    old.write_text("{}")
    new = mod.JSON_HISTORY_DIR / "ip-ranges-20990101-0000.json"
    new.write_text("{}")

    mod.prune_history()

    remaining = {p.name for p in mod.JSON_HISTORY_DIR.glob("ip-ranges-*.json")}
    assert remaining == {new.name}


def test_prune_history_keeps_sole_snapshot_even_if_old():
    tmp = Path(tempfile.mkdtemp())
    mod = _load_module(tmp)
    mod.JSON_HISTORY_DIR.mkdir(parents=True)

    only = mod.JSON_HISTORY_DIR / "ip-ranges-20200101-0000.json"
    only.write_text("{}")

    mod.prune_history()

    assert only.exists()


if __name__ == "__main__":
    sys.exit(__import__("pytest").main([__file__, "-v"]))
