# SPDX-License-Identifier: Apache-2.0
# Parquet snapshot design adapted from Russell Spitzer's iceberg-community-health.
"""Atomic local snapshots. Internal records never become public exports."""
import hashlib
import json
import os
import uuid
from pathlib import Path

import duckdb


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def get(self, source):
        info = self.state.get(source, {})
        if not info.get("snapshot"):
            return []
        with duckdb.connect() as db:
            rows = db.execute("SELECT payload FROM read_parquet(?)", [str(self.root / info["snapshot"])]).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save(self, source, rows, info):
        # The source collector returns the reconciled state, not an append-only
        # list. Replacing it removes confirmed deletions on a full refresh.
        rows = sorted({row["id"]: row for row in rows}.values(), key=lambda r: r["id"])
        payload = json.dumps(rows, sort_keys=True)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        relative = f"snapshots/{source.replace(':', '-')}-{digest[:20]}.parquet"
        target = self.root / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".tmp.parquet")
            with duckdb.connect() as db:
                db.execute("CREATE TABLE records(payload VARCHAR)")
                if rows:
                    db.executemany("INSERT INTO records VALUES (?)", [(json.dumps(row, sort_keys=True),) for row in rows])
                escaped = str(temporary).replace("'", "''")
                db.execute(f"COPY records TO '{escaped}' (FORMAT PARQUET)")
            os.replace(temporary, target)
        self.state[source] = dict(info, snapshot=relative, digest=digest, records=len(rows))
        atomic_json(self.state_path, self.state)

    def fail(self, source, status, reason, attempted_at):
        previous = self.state.get(source, {})
        self.state[source] = dict(previous, status=status, reason=reason, attempted_at=attempted_at)
        atomic_json(self.state_path, self.state)
