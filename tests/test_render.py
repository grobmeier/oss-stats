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


def test_interrupted_discussion_collection_can_render_without_observations(tmp_path):
    store = Store(tmp_path)
    store.save("log4j:discussions", [{"id": "d1", "title": "Question", "url": "https://github.com/a/b/discussions/1", "created_at": "2026-11-01T00:00:00Z",
               "updated_at": "2026-11-02T00:00:00Z", "actor": "U1", "state": "open", "history": "observed", "observations": [], "comments": []}], {"status": "partial"})
    config = load()
    config["history_months"] = 1
    report = build_report(store, config, "2026-11-16T00:00:00Z")
    assert report["waiting"]["log4j"] == []


def test_quarterly_report_recomputes_observations_instead_of_monthly_medians(tmp_path):
    from datetime import timedelta
    from logging_stats.timeutil import norm_ts, parse_ts
    store = Store(tmp_path)
    rows = []
    for n in range(11):
        created = "2026-01-01T00:00:00Z" if n == 0 else "2026-02-01T00:00:00Z"
        reply = norm_ts((parse_ts(created) + timedelta(hours=1 if n == 0 else 100)).isoformat())
        rows.append({"id": str(n), "created_at": created, "actor": "author", "history": "events", "events": [],
                     "comments": [{"actor": "other", "at": reply}], "state": "closed", "closed_at": reply})
    store.save("log4j:issues", rows, {"status": "complete"})
    config = load()
    config.update(history_months=3, sample_floor=1)
    report = build_report(store, config, "2026-04-05T00:00:00Z")
    row = next(r for r in report["metrics"] if r["scope"] == "log4j" and r["metric"] == "issue_reply_hours" and r["grouping"] == "quarterly")
    assert row["value"] == 100


def test_transferred_items_count_once_and_release_metrics_stay_per_project(tmp_path):
    store = Store(tmp_path)
    for pid in ("log4j", "kotlin"):
        store.save(pid+":issues", [{"id": "same-global-node", "created_at": "2026-10-01T00:00:00Z", "state": "closed",
                   "closed_at": "2026-10-02T00:00:00Z", "actor": "U1", "events": [], "comments": []}], {"status": "complete"})
    config = load()
    config["history_months"] = 1
    report = build_report(store, config, "2026-11-16T00:00:00Z")
    row = next(r for r in report["metrics"] if r["scope"] == "logging" and r["metric"] == "issues_opened" and r["grouping"] == "monthly")
    assert row["value"] == 1
    assert not any(r["scope"] == "logging" and r["metric"] == "stable_releases" for r in report["metrics"])
