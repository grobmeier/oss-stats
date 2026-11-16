from logging_stats.store import Store


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
