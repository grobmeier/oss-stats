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
