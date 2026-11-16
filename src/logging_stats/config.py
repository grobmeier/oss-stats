# SPDX-License-Identifier: Apache-2.0
"""Project catalogue and internal identity rules."""
import hashlib
import re
from pathlib import Path

import yaml


def load(path=Path("config/logging.yaml")):
    config = yaml.safe_load(Path(path).read_text())
    ids = [p["id"] for p in config["projects"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Project IDs must be unique")
    dashboard = config.setdefault("dashboard_id", "logging")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", dashboard):
        raise ValueError("Dashboard ID must contain lowercase letters, digits, or hyphens")
    if not ids or any(not re.fullmatch(r"[a-z][a-z0-9-]*", pid) or pid in (dashboard, "index", "shared-list") for pid in ids):
        raise ValueError("Project IDs must be safe, unique page names and differ from the dashboard ID")
    for project in config["projects"]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", project["repo"]):
            raise ValueError("Repository must use owner/name syntax")
        project.setdefault("release_pattern", r"v?(?P<version>\d+\.\d+\.\d+)")
        pattern = re.compile(project["release_pattern"])
        if "version" not in pattern.groupindex:
            raise ValueError("Release pattern must contain a named version group")
    base = config.setdefault("base_path", f"/{dashboard}/")
    if not re.fullmatch(r"/[a-z][a-z0-9-]*/", base):
        raise ValueError("Base path must contain one safe directory, such as /logging/")
    config.setdefault("brand", config["title"])
    config.setdefault("inactive", [])
    config.setdefault("bot_patterns", [r"\[bot\]$", r"^dependabot", r"^renovate"])
    config.setdefault("data_dir", f"data/{dashboard}")
    config.setdefault("output_dir", f"site/{dashboard}")
    config.setdefault("history_months", 72)
    config.setdefault("sample_floor", 5)
    config.setdefault("stale_days", 28)
    return config


def identity(value, config):
    if not value:
        return None
    value = str(value).strip().lower()
    if any(re.search(pattern, value) for pattern in config["bot_patterns"]):
        return None
    return config.get("identity_aliases", {}).get(value, value)


def email_identity(value, config):
    value = identity(value, config)
    return "mail:" + hashlib.sha256(value.encode()).hexdigest() if value else None


def modules(paths, project):
    return sorted({name for name, prefixes in project.get("modules", {}).items()
                   if any(path.startswith(prefix) for path in paths for prefix in prefixes)})
