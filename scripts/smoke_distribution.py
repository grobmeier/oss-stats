#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check an extracted executable using synthetic data outside the checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

import yaml

from logging_stats.config import load
from logging_stats.store import Store


def smoke(archive):
    with tempfile.TemporaryDirectory(prefix="logging-stats-smoke-") as temporary:
        work = Path(temporary)
        with tarfile.open(archive) as stream:
            stream.extractall(work, filter="data")
        package = next(p for p in work.iterdir() if p.is_dir())
        manifest = json.loads((package / "BUILD.json").read_text())
        for relative, digest in manifest["files"].items():
            assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == digest, relative
        executable = package / "logging-stats"
        outside = work / "outside-checkout"
        outside.mkdir()
        # Render must not depend on Git, gh, Python executables, or the source checkout.
        environment = dict(os.environ, PATH="/nonexistent")
        environment.pop("PYTHONPATH", None)
        subprocess.run([str(executable), "--help"], cwd=outside, env=environment, check=True, capture_output=True)
        for name in ("logging", "maven", "commons"):
            config = yaml.safe_load((package / "config" / (name + ".yaml")).read_text())
            config["history_months"] = 2
            config_path = outside / (name + ".yaml")
            config_path.write_text(yaml.safe_dump(config))
            config = load(config_path)
            data = outside / (name + "-data")
            store = Store(data)
            store.bind(config)
            for project in config["projects"]:
                for source in ("metadata", "commits", "pulls", "issues", "discussions", "releases"):
                    rows = [{"id": "synthetic-commit", "actor": "synthetic-person", "at": "2026-10-02T00:00:00Z"}] if source == "commits" else []
                    store.save(project["id"] + ":" + source, rows, {"status": "complete"})
            if config.get("mail"):
                store.save(name + ":mail", [], {"status": "complete"})
            output = outside / (name + "-site")
            subprocess.run([str(executable), "--config", str(config_path), "--data", str(data), "render",
                            "--output", str(output), "--as-of", "2026-11-16T19:18:27Z"],
                           cwd=outside, env=environment, check=True, capture_output=True)
            report = json.loads((output / "metrics.json").read_text())
            row = next(r for r in report["metrics"] if r["scope"] == name and r["metric"] == "commits" and r["grouping"] == "monthly" and r["start"].startswith("2026-10"))
            assert row["value"] == len(config["projects"])
            assert len(list(output.glob("*.html"))) == len(config["projects"]) + 1
            assert "Russell Spitzer" in (output / "index.html").read_text()
            assert "function ageBars" in (output / "app.js").read_text()
            assert (output / "view.js").is_file() and (output / "style.css").is_file()
            print("Standalone render passed:", name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    smoke(parser.parse_args().archive)
