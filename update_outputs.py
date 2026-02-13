#!/usr/bin/env python3
"""
Generate docs/output/*.txt and docs/index.html for databricksIPranges.
Run locally or from GitHub Actions. Uses extract-databricks-ips.py (no extra deps).
"""

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DOCS = REPO_ROOT / "docs"
OUTPUT_DIR = DOCS / "output"
JSON_HISTORY_DIR = DOCS / "json-history"
SOURCE_URL = "https://www.databricks.com/networking/v1/ip-ranges.json"
GITHUB_REPO = "https://github.com/bhavink/databricksIPranges"
PAGES_URL = "https://bhavink.github.io/databricksIPranges"
LINKEDIN_URL = "https://www.linkedin.com/in/bhavink"


def load_extract_module():
    """Load extract-databricks-ips.py as a module (filename has hyphen)."""
    script = REPO_ROOT / "extract-databricks-ips.py"
    spec = importlib.util.spec_from_file_location("extract_module", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    DOCS.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    JSON_HISTORY_DIR.mkdir(exist_ok=True)

    mod = load_extract_module()
    data = mod.load_ip_ranges()

    # Optional: save raw JSON for history (one per run); capture revision for index
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    history_file = JSON_HISTORY_DIR / f"ip-ranges-{ts}.json"
    revision_display = "—"
    latest_history_basename = None
    try:
        import urllib.request
        with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
        with open(history_file, "w") as f:
            json.dump(raw_data, f, indent=2)
        latest_history_basename = history_file.name
        rev = raw_data.get("schemaVersion") or raw_data.get("timestampSeconds")
        revision_display = str(rev) if rev is not None else "—"
    except Exception:
        pass  # skip history on failure

    # Outputs: per cloud (all types) + per cloud outbound only + all
    outputs = [
        ("aws", "all", "aws.txt"),
        ("aws", "outbound", "aws-outbound.txt"),
        ("azure", "all", "azure.txt"),
        ("azure", "outbound", "azure-outbound.txt"),
        ("gcp", "all", "gcp.txt"),
        ("gcp", "outbound", "gcp-outbound.txt"),
        ("all", "all", "all.txt"),
    ]

    for cloud, type_filter, filename in outputs:
        filtered = mod.extract_ips(
            data, cloud=cloud, region="all", type_filter=type_filter
        )
        out_str = mod.format_output(
            filtered, data, cloud, "all", "simple"
        )
        (OUTPUT_DIR / filename).write_text(out_str.strip() + "\n" if out_str else "")

    # Directory index for output/ (like azureIPranges ranges-services-pa)
    txt_files = [fn for (_, _, fn) in outputs]
    output_index_lines = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head><meta charset=\"UTF-8\"><title>Directory Index – Databricks IP Ranges</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;max-width:600px;margin:2em auto;padding:0 20px;} a{color:#0969da;} ul{list-style:none;padding-left:0;} li{margin:6px 0;}</style>",
        "</head><body>",
        "<h1>Directory Index</h1>",
        "<p>Click on a file to download:</p>",
        "<ul>",
    ]
    for fn in sorted(txt_files):
        output_index_lines.append(f'  <li><a href="{fn}">{fn}</a></li>')
    output_index_lines.append("</ul>")
    output_index_lines.append(f"<p><a href=\"../index.html\">Back to databricksIPranges</a></p>")
    output_index_lines.append("</body></html>")
    (OUTPUT_DIR / "index.html").write_text("\n".join(output_index_lines))

    # Directory index for json-history/ (GitHub Pages doesn't list directories)
    json_files = sorted(JSON_HISTORY_DIR.glob("*.json"), reverse=True)  # newest first
    history_index_lines = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head><meta charset=\"UTF-8\"><title>JSON History – Databricks IP Ranges</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;max-width:640px;margin:2em auto;padding:0 20px;} a{color:#0969da;} ul{list-style:none;padding-left:0;} li{margin:8px 0;}</style>",
        "</head><body>",
        "<h1>JSON History</h1>",
        "<p>Snapshot of the official Databricks IP ranges JSON per run. Click to download.</p>",
        "<ul>",
    ]
    for f in json_files:
        history_index_lines.append(f'  <li><a href="{f.name}">{f.name}</a></li>')
    history_index_lines.append("</ul>")
    history_index_lines.append("<p><a href=\"../index.html\">Back to databricksIPranges</a></p>")
    history_index_lines.append("</body></html>")
    (JSON_HISTORY_DIR / "index.html").write_text("\n".join(history_index_lines))

    # Generate docs/index.html (azureIPranges-style for Databricks AWS/Azure/GCP)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    latest_json_link = f'<a href="json-history/{latest_history_basename}">{latest_history_basename}</a>' if latest_history_basename else "—"
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Databricks IP Ranges – AWS, Azure, GCP</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; color: #24292f; }}
    h1 {{ border-bottom: 1px solid #d0d7de; padding-bottom: 8px; }}
    h2 {{ margin-top: 24px; color: #0969da; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    ul {{ padding-left: 24px; }}
    .meta {{ color: #656d76; font-size: 14px; margin-top: 24px; }}
    .disclaimer {{ margin-top: 32px; padding: 12px; background: #f6f8fa; border-radius: 6px; font-size: 13px; color: #656d76; }}
  </style>
</head>
<body>
  <h1>Databricks IP Ranges – AWS, Azure, GCP</h1>

  <h2>Source JSON Files</h2>
  <p><strong>Revision / schema version:</strong> {revision_display}</p>
  <p><strong>Official source (JSON):</strong> <a href="{SOURCE_URL}">ip-ranges.json</a> — Databricks' machine-readable IP ranges. <em>Official docs page: Coming Soon.</em></p>
  <p><strong>Latest snapshot on this site:</strong> {latest_json_link}</p>
  <p><strong>Previous JSON versions:</strong> <a href="json-history/">View JSON History</a></p>

  <h2>Palo Alto Networks Ready Files</h2>
  <p>Formatted TXT files for Palo Alto Networks firewalls are available on this page: <a href="output/">output/</a></p>
  <p>Each file is organized by cloud and type (e.g. <code>aws.txt</code>, <code>azure-outbound.txt</code>, <code>gcp.txt</code>). Download the file you need and import it into your PA firewall configuration.</p>

  <h2>Automation-Friendly Design</h2>
  <p>This page was created to simplify the integration of Databricks IP ranges into firewalls. The project provides a static link to the latest JSON and per-cloud TXT files so you can automate allowlisting without parsing the official API response each time.</p>

  <h2>Databricks IP Ranges Script</h2>
  <p>This page is automatically generated using a Python script available at <a href="{GITHUB_REPO}">GitHub Repository</a>, and updated regularly through <a href="{GITHUB_REPO}/actions">GitHub Actions</a>.</p>
  <p>We recommend forking this script if you plan to automate your infrastructure with it. Forking ensures you maintain control of updates, can customize it for your environment, and enhance security by avoiding dependencies on this repository.</p>
  <p><strong>Features</strong></p>
  <ul>
    <li>Fetches the latest Databricks IP ranges JSON (AWS, Azure, GCP)</li>
    <li>Processes and organizes IP ranges by cloud and type (inbound/outbound)</li>
    <li>Generates individual TXT files per cloud/type compatible with PA firewalls (one CIDR per line)</li>
    <li>Provides a static JSON link and optional history of JSON snapshots</li>
    <li>Maintains a history of JSON files for reference</li>
  </ul>
  <p><strong>Note:</strong> Databricks may update IP ranges periodically. Always verify the ranges against your requirements before implementation. Availability may vary by cloud and region.</p>

  <h2>Contact</h2>
  <p><a href="{LINKEDIN_URL}">Connect on LinkedIn</a> · <a href="{GITHUB_REPO}">Reach on GitHub</a></p>

  <p class="meta">Generated on {now_utc} by GitHub Automation</p>
  <div class="disclaimer">This page, its contents, and the associated repository are provided "AS IS" without warranty of any kind. Please refer to the README in the repository for the full disclaimer.</div>
</body>
</html>
"""
    (DOCS / "index.html").write_text(index_html)
    print("Generated docs/output/*.txt, docs/output/index.html, docs/json-history/index.html, and docs/index.html")


if __name__ == "__main__":
    main()
