import json

from logging_stats.config import load
from logging_stats.metrics import build_report
from logging_stats.render import publish
from logging_stats.store import Store


def test_static_report_pages_exports_and_atomic_replacement(tmp_path):
    store = Store(tmp_path / "data")
    store.save("kotlin:discussions", [], {"status": "disabled"})
    config = load()
    config["history_months"] = 3
    report = build_report(store, config, "2026-11-16T00:00:00Z")
    report["waiting"]["log4j"] = [{"title": "<script> owner@example.com", "url": "https://github.com/example"}]
    output = tmp_path / "site" / "logging"
    publish(report, output)
    first = output.resolve()
    assert all((output / (p["id"] + ".html")).exists() for p in config["projects"])
    public = (output / "metrics.json").read_text()
    assert "owner@example.com" not in public
    assert "identity_aliases" not in public
    assert "snapshot" not in json.loads(public)["sources"]["kotlin:discussions"]
    assert (output / "metrics.csv").exists()
    assert "Russell Spitzer" in (output / "index.html").read_text()
    assert "./app.js" in (output / "log4j.html").read_text()
    publish(report, output)
    assert output.resolve() != first and first.exists()
    assert all(r["value"] is None for r in report["metrics"] if r["scope"] == "kotlin" and r["metric"].startswith("discussion"))


def test_ecosystem_deduplicates_participants(tmp_path):
    store = Store(tmp_path)
    for pid in ("log4j", "kotlin"):
        store.save(pid+":commits", [{"id": "same-sha", "actor": "same-person", "at": "2026-10-10T00:00:00Z"}], {"status": "complete"})
    config = load()
    config["history_months"] = 1
    report = build_report(store, config, "2026-11-16T00:00:00Z")
    row = next(r for r in report["metrics"] if r["scope"] == "logging" and r["metric"] == "commit_authors" and r["grouping"] == "monthly")
    assert row["value"] == 1
