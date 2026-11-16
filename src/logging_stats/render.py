# SPDX-License-Identifier: Apache-2.0
"""Static HTML, aggregate JSON, CSV, and atomic snapshot publication."""
import csv
import json
import os
import re
import tempfile
import uuid
from html import escape
from pathlib import Path


def public_text(value):
    return re.sub(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[address omitted]", value)


def publish(report, output):
    output = Path(output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not output.is_symlink():
        raise ValueError("Output must be absent or a snapshot symlink. Choose a new output path.")
    # Work on a detached report so sanitising public titles never changes data.
    report = json.loads(json.dumps(report))
    for rows in report["waiting"].values():
        for row in rows:
            row["title"] = public_text(row["title"])
    snapshots = output.parent / ("." + output.name + "-snapshots")
    snapshots.mkdir(exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="report-", dir=snapshots))
    (target / "metrics.json").write_text(json.dumps(report, separators=(",", ":"), ensure_ascii=False))
    fields = ("scope", "metric", "start", "end", "grouping", "value", "n", "status", "reason")
    with (target / "metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report["metrics"])
    assets = Path(__file__).with_name("web")
    for asset in assets.iterdir():
        (target / asset.name).write_bytes(asset.read_bytes())
    for scope, title in [(report.get("dashboard_id", "logging"), report["title"])] + [(p["id"], p["name"]) for p in report["projects"]]:
        filename = "index.html" if scope == report.get("dashboard_id", "logging") else scope + ".html"
        (target / filename).write_text(page(scope, title, report))
    # Swap one symlink only after the entire version is ready. A failed build
    # leaves the previous output reachable. Retain earlier local versions.
    temporary = output.with_name(output.name + "." + uuid.uuid4().hex)
    temporary.symlink_to(target.relative_to(output.parent), target_is_directory=True)
    os.replace(temporary, output)


def page(scope, title, report):
    brand = escape(report.get("brand", report["title"]))
    navigation = ''.join(f'<a href="./{escape(p["id"])}.html">{escape(p["name"])}</a>' for p in report["projects"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Independent community activity dashboard with explicit data coverage.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%23183c35'/%3E%3Ctext x='10' y='43' fill='white' font-family='sans-serif' font-size='32'%3ELS%3C/text%3E%3C/svg%3E">
<title>{escape(title)} · {brand}</title><link rel="stylesheet" href="./style.css">
<script src="./view.js" defer></script><script src="./app.js" defer></script></head>
<body data-scope="{escape(scope)}"><a class="skip" href="#main">Skip to dashboard</a>
<header><div class="brand">{brand} <span>Independent community observatory</span></div>
<nav aria-label="Projects"><a href="./index.html">Overview</a>{navigation}</nav></header>
<main id="main"><p class="eyebrow">PUBLIC COMMUNITY ACTIVITY</p><h1>{escape(title)}</h1>
<p class="intro">Contributions, conversations, and work awaiting a response. Each measurement includes its source coverage.</p>
<p id="freshness" role="status">Loading the local report…</p><button id="reload" type="button">Reload published report</button>
<p class="scope-note">Reload checks the latest published snapshot. Collection and publication run separately.</p><div id="warning"></div>
<form id="filters"><label>From <input id="from" type="month"></label><label>To <input id="to" type="month"></label>
<label>Group by <select id="group"><option value="monthly">Month</option><option value="quarterly">Quarter</option><option value="partial month">Current partial month</option></select></label>
<label>Range <select id="range"><option value="12">Last year</option><option value="36">Last 3 years</option><option value="72">Last 6 years</option><option value="custom">Custom</option></select></label>
<label id="module-label" hidden>Module <select id="module"><option value="">All modules</option></select></label><button id="reset" type="button">Reset filters</button></form>
<p id="range-status" role="status"></p><nav id="sections" aria-label="Dashboard sections"></nav>
<div id="dashboard"></div><noscript>This dashboard needs JavaScript for filters. Download the aggregate CSV for a plain data view.</noscript>
<section id="methodology"><h2>Methodology and limits</h2><p>Activity does not measure individual effort, project quality, support commitments, or security.</p>
<p>Periods use UTC and exclude their end timestamp. Counts remain visible at small sample sizes. Rates and medians require five observations.</p>
<p>Monthly and quarterly values are computed separately from observations. Unique people are counted once per channel across projects.
Git identities, GitHub accounts, and mail senders remain separate. Module counts overlap.</p>
<p>Response medians include answered items only. Unanswered counts use the same cohort and period end. Recent cohorts have less observation time.</p>
<p>Historical answer state uses observed snapshots only. Legacy JIRA and other mailing lists are outside coverage.
Newcomer labels require known identity history. Archive entries without publication dates remain undated.</p>
<details><summary>Metric definitions</summary><dl id="definitions"></dl></details></section>
<section id="coverage"><h2>Coverage</h2><p>Disabled, failed, partial, and unavailable sources are distinct from zero activity. Retained records can be older than this report.</p><div id="sources" class="table-wrap"></div></section>
<p class="downloads"><a href="./metrics.json">Aggregate JSON</a> · <a href="./metrics.csv">Aggregate CSV</a></p>
</main><footer>Adapted from <a href="https://github.com/RussellSpitzer/iceberg-community-health">Russell Spitzer’s Iceberg Community Health</a>.
<a href="https://github.com/grobmeier/logging-stats">Source and provenance</a>. Apache-2.0. Independent project, without claimed ASF endorsement.</footer></body></html>'''
