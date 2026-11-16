from logging_stats.store import Store
from logging_stats.config import load
import json


def test_idempotent_snapshot_and_failure_preserves_records(tmp_path):
    store = Store(tmp_path)
    rows = [{"id": "one", "value": 1}]
    store.save("log4j:issues", rows * 2, {"status": "complete", "last_success": "2026-11-16T00:00:00Z"})
    snapshot = store.state["log4j:issues"]["snapshot"]
    store.save("log4j:issues", rows, {"status": "complete"})
    assert store.state["log4j:issues"]["snapshot"] == snapshot
    store.fail("log4j:issues", "failed", "source unavailable", "2026-11-16T00:00:00Z")
    assert store.get("log4j:issues") == rows
    store.save("log4j:issues", [], {"status": "complete"})
    assert store.get("log4j:issues") == []


def test_manifests_preserve_immutable_source_snapshot_provenance(tmp_path):
    store = Store(tmp_path)
    store.save("log4j:issues", [{"id": "first"}], {"status": "complete", "last_success": "2026-11-16T00:00:00Z"})
    path = store.manifest(load(), "2026-11-16T00:00:00Z")
    store.save("log4j:issues", [{"id": "second"}], {"status": "complete"})
    recorded = json.loads(path.read_text())
    assert recorded["definition_version"] == "1.0"
    assert recorded["sources"]["log4j:issues"]["snapshot"] != store.state["log4j:issues"]["snapshot"]
