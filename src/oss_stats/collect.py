# Copyright 2026 Christian Grobmeier and contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
# Collection approach adapted from Russell Spitzer's iceberg-community-health.
"""Normalise public sources without retaining message or comment bodies."""
import html
import json
import re
import subprocess
import time
from urllib.error import URLError
import urllib.request
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

from . import __version__
from .config import email_identity, identity, modules
from .github import COMMENTS, DISCUSSIONS, REPLIES, item_query
from .timeutil import norm_ts, parse_ts


def now():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def actor(user, config):
    if not user or user.get("type", user.get("__typename")) == "Bot":
        return None
    if identity(user.get("login"), config) is None:
        return None
    return "github:" + str(user.get("node_id") or user.get("id") or user["login"])


def normal_comment(comment, config, graphql=False):
    return {"id": str(comment["id"]), "at": norm_ts(comment.get("createdAt") if graphql else comment.get("created_at")),
            "actor": actor(comment.get("author") if graphql else comment.get("user"), config)}


def normal_event(event):
    name = event.get("event")
    if name not in {"closed", "reopened", "merged", "ready_for_review", "convert_to_draft", "converted_to_discussion"}:
        return None
    at = norm_ts(event.get("created_at"))
    return {"id": str(event.get("id", f"{name}:{at}")), "kind": name, "at": at} if at else None


def collect_items(api, project, config, kind, since, previous=(), limit=None, checkpoint=None):
    repo = project["repo"]
    endpoint = f"repos/{repo}/issues?state=all&sort=updated&direction=desc&since={since}"
    # The issue index also includes PRs. Never infer a PR's draft or merge
    # state from that index. Read its dedicated resource.
    index = api.pages(endpoint, limit=max(100, limit * 10) if limit else None)
    if not limit:
        # Old, unchanged open items can predate the history window.
        opened = api.pages(f"repos/{repo}/issues?state=open")
        index = list({r["node_id"]: r for r in index + opened}.values())
    index = [r for r in index if ("pull_request" in r) == (kind == "pulls")]
    if limit:
        index = index[:limit]
    records = {r["id"]: r for r in previous}
    observed_ids = set()
    for item in index:
        observed_ids.add(str(item["node_id"]))
        old = records.get(str(item["node_id"]))
        if old and old.get("updated_at") == norm_ts(item["updated_at"]) and old.get("details_complete"):
            continue
        number = item["number"]
        root = f"repos/{repo}"
        pull = api.call(f"{root}/pulls/{number}") if kind == "pulls" else item
        timeline = api.pages(f"{root}/issues/{number}/timeline")
        comments = api.pages(f"{root}/issues/{number}/comments")
        events = [parsed for event in timeline if (parsed := normal_event(event))]
        record = {
            "id": str(item["node_id"]), "number": number, "title": item["title"],
            "url": item["html_url"], "created_at": norm_ts(item["created_at"]),
            "updated_at": norm_ts(item["updated_at"]), "closed_at": norm_ts(item.get("closed_at")),
            "state": item["state"], "actor": actor(item.get("user"), config),
            "comments": [normal_comment(c, config) for c in comments], "events": events,
            "history": "events", "kind": kind, "details_complete": True,
        }
        if kind == "pulls":
            reviews = api.pages(f"{root}/pulls/{number}/reviews")
            files = api.pages(f"{root}/pulls/{number}/files")
            # REST caps changed files at 3000. Mark the entire source partial
            # rather than presenting incomplete module coverage as complete.
            if len(files) >= 3000:
                raise RuntimeError("PR changed-file limit reached. Module coverage is incomplete.")
            record.update(draft=pull["draft"], merged_at=norm_ts(pull.get("merged_at")),
                          modules=modules([f["filename"] for f in files], project),
                          reviews=[{"id": str(r["id"]), "actor": actor(r.get("user"), config),
                                    "at": norm_ts(r.get("submitted_at"))} for r in reviews if r.get("submitted_at")])
        records[record["id"]] = record
        if checkpoint and len(observed_ids) % 25 == 0:
            checkpoint(list(records.values()))
    return list(records.values())


def collect_discussions(api, project, config, previous=(), since=None, limit=None, checkpoint=None):
    owner, name = project["repo"].split("/")
    discussions = api.connection(DISCUSSIONS, {"owner": owner, "name": name},
                                 lambda d: d["repository"]["discussions"], limit)
    old_records = {r["id"]: r for r in previous}
    records = dict(old_records) if since else {}
    def expand(initial, query, node_id, field):
        rows = list(initial["nodes"])
        seen = set()
        while initial["pageInfo"]["hasNextPage"]:
            cursor = initial["pageInfo"]["endCursor"]
            if not cursor or cursor in seen:
                raise RuntimeError("Discussion pagination stopped advancing")
            seen.add(cursor)
            initial = api.call("graphql", query, {"id": node_id, "cursor": cursor})["node"][field]
            rows.extend(initial["nodes"])
        return rows
    for index, item in enumerate(discussions, 1):
        if since and item["updatedAt"] < since and item["id"] in records:
            continue
        comments = expand(item["comments"], COMMENTS, item["id"], "comments") if "comments" in item else api.connection(COMMENTS, {"id": item["id"]}, lambda d: d["node"]["comments"])
        replies = []
        for comment in comments:
            replies.extend(expand(comment["replies"], REPLIES, comment["id"], "replies") if "replies" in comment else api.connection(REPLIES, {"id": comment["id"]}, lambda d: d["node"]["replies"]))
        record = {
            "id": item["id"], "number": item["number"], "title": item["title"], "url": item["url"],
            "created_at": norm_ts(item["createdAt"]), "updated_at": norm_ts(item["updatedAt"]),
            "state": "closed" if item["closed"] else "open", "closed_at": norm_ts(item.get("closedAt")),
            "actor": actor(item.get("author"), config), "category": item["category"]["name"],
            "answerable": item["category"]["isAnswerable"], "answer_id": (item.get("answer") or {}).get("id"),
            "answer_at": norm_ts(item.get("answerChosenAt")), "history": "observed", "kind": "discussions",
            "comments": [normal_comment(c, config, True) for c in comments + replies],
        }
        # GraphQL does not expose an answer-removal timeline. Retain observed
        # states instead of assigning today's answer backwards through history.
        record["observations"] = old_records.get(record["id"], {}).get("observations", [])
        records[record["id"]] = record
        if checkpoint and index % 10 == 0:
            checkpoint(list(records.values()))
    return list(records.values())


def collect_batched_items(api, project, config, kind, since, previous=(), limit=None, checkpoint=None, full=False):
    owner, name = project["repo"].split("/")
    collection = "pullRequests" if kind == "pulls" else "issues"
    records = {r["id"]: r for r in previous}
    seen = set()
    type_map = {"ClosedEvent": "closed", "ReopenedEvent": "reopened", "ConvertedToDiscussionEvent": "converted_to_discussion",
                "MergedEvent": "merged", "ReadyForReviewEvent": "ready_for_review", "ConvertToDraftEvent": "convert_to_draft"}
    def expand(item, field):
        initial = item[field]
        rows = list(initial["nodes"])
        cursor = initial["pageInfo"]["endCursor"]
        visited = set()
        while initial["pageInfo"]["hasNextPage"]:
            if not cursor or cursor in visited:
                raise RuntimeError("Nested pagination stopped advancing")
            visited.add(cursor)
            initial = api.call("graphql", item_query(kind, field), {"id": item["id"], "cursor": cursor})["node"][field]
            rows.extend(initial["nodes"])
            cursor = initial["pageInfo"]["endCursor"]
        if "totalCount" in item[field] and len(rows) != item[field]["totalCount"]:
            raise RuntimeError("GitHub connection count differs from fetched records. Coverage is incomplete.")
        return rows
    processed = 0
    for open_only in (False, True):
        cursor, cursors = None, set()
        stop = False
        while not stop:
            result = api.call("graphql", item_query(kind, open_only=open_only), {"owner": owner, "name": name, "cursor": cursor})
            connection = result["repository"][collection]
            for item in connection["nodes"]:
                if not full and not open_only and item["updatedAt"] < since:
                    stop = True
                    break
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                old = records.get(item["id"])
                if not full and old and old.get("updated_at") == norm_ts(item["updatedAt"]) and old.get("details_complete"):
                    continue
                events = expand(item, "timelineItems")
                row = {"id": item["id"], "number": item["number"], "title": item["title"], "url": item["url"],
                       "created_at": norm_ts(item["createdAt"]), "updated_at": norm_ts(item["updatedAt"]),
                       "closed_at": norm_ts(item.get("closedAt")), "state": "open" if item["state"] == "OPEN" else "closed",
                       "actor": actor(item.get("author"), config), "kind": kind, "history": "events", "details_complete": True,
                       "comments": [normal_comment(c, config, True) for c in expand(item, "comments")],
                       "events": [{"id": e["id"], "at": norm_ts(e["createdAt"]), "kind": type_map[e["__typename"]]} for e in events]}
                if kind == "pulls":
                    row.update(draft=item["isDraft"], merged_at=norm_ts(item.get("mergedAt")),
                               reviews=[{"id": r["id"], "actor": actor(r.get("author"), config), "at": norm_ts(r["submittedAt"])}
                                        for r in expand(item, "reviews") if r.get("submittedAt")],
                               modules=modules([f["path"] for f in expand(item, "files")], project))
                records[row["id"]] = row
                processed += 1
                if checkpoint and processed % 25 == 0:
                    checkpoint(list(records.values()))
                if processed % 250 == 0:
                    print(f"  {project['id']}:{kind}: {processed} items read", flush=True)
                if limit and processed >= limit:
                    return list(records.values())
            info = connection["pageInfo"]
            if not info["hasNextPage"]:
                break
            cursor = info["endCursor"]
            if not cursor or cursor in cursors:
                raise RuntimeError("Item pagination stopped advancing")
            cursors.add(cursor)
        if full or limit:
            # A full traversal already includes old open items.
            break
    return [row for key, row in records.items() if not full or key in seen]


def git_records(project, config, cache, start):
    destination = Path(cache) / project["id"]
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--bare", "--filter=blob:none", "https://github.com/" + project["repo"] + ".git", str(destination)],
                       check=True, capture_output=True, timeout=600)
    branch = project["branch"]
    branches = list(dict.fromkeys([branch] + project.get("branches", [])))
    records = {}
    for branch in branches:
        subprocess.run(["git", "--git-dir", str(destination), "fetch", "--quiet", "https://github.com/" + project["repo"] + ".git", f"+refs/heads/{branch}:refs/heads/{branch}", "--tags"],
                       check=True, capture_output=True, timeout=600)
        output = subprocess.run(["git", "--git-dir", str(destination), "log", branch, "--no-merges", "--no-renames", "--use-mailmap",
                                 "--format=COMMIT %H%x09%aE%x09%aI", "--name-only"],
                                check=True, capture_output=True, text=True, timeout=600).stdout
        current, paths = None, []
        def save():
            if current:
                sha, email, at = current
                records[sha] = {"id": sha, "at": norm_ts(at), "actor": email_identity(email, config),
                                "modules": modules(paths, project)}
        for line in output.splitlines():
            if line.startswith("COMMIT "):
                save()
                current, paths = line[7:].split("\t"), []
            elif line.strip():
                paths.append(line.strip())
        save()
    # Keep full author history to distinguish new cohorts from first observed.
    return list(records.values())


def read_url(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": f"oss-stats/{__version__} (+https://github.com/grobmeier/oss-stats)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_mbox(raw, config):
    if raw.lstrip().lower().startswith((b"{", b"<html", b"<!doctype")):
        raise RuntimeError("The mailing archive returned an error document instead of an mbox")
    rows = []
    chunks = re.split(br"(?m)^From [^\n]*\n", raw)
    for chunk in chunks:
        message = BytesParser(policy=policy.default).parsebytes(chunk, headersonly=True)
        message_id, date = str(message.get("Message-ID") or "").strip(), message.get("Date")
        if not message_id or not date:
            continue
        references = re.findall(r"<[^>]+>", str(message.get("References") or message.get("In-Reply-To") or ""))
        rows.append({"id": message_id, "at": norm_ts(parsedate_to_datetime(str(date)).isoformat()),
                     "actor": email_identity(parseaddr(str(message.get("From") or ""))[1], config),
                     "parent": references[-1] if references else None,
                     "root": references[0] if references else message_id,
                     "threading": "references" if references else "root-or-unlinked"})
    return rows


def mail_records(config, starts):
    mail = config["mail"]
    rows = []
    for month in starts:
        url = f"https://lists.apache.org/api/mbox.lua?list={mail['list']}&domain={mail['domain']}&d={month}"
        for attempt in range(3):
            try:
                raw = read_url(url, timeout=180)
                break
            except (TimeoutError, URLError) as error:
                if attempt == 2 or (hasattr(error, "code") and error.code not in (429, 500, 502, 503, 504)):
                    raise
                time.sleep(2 * (attempt + 1))
        rows.extend(parse_mbox(raw, config))
    return rows


def archive_versions(text, project):
    pattern = re.compile(project["release_pattern"])
    found = {}
    for href in re.findall(r'href="([^"]+)"', text):
        name = html.unescape(href).rstrip("/")
        match = pattern.fullmatch(name)
        if match:
            version = match["version"].replace("_", ".")
            if project.get("release_majors") and int(version.split(".")[0]) not in project["release_majors"]:
                continue
            found[version] = urljoin(project["archive"], href)
    return found


def release_records(api, project):
    if not project.get("archive"):
        rows = []
        for release in api.pages(f"repos/{project['repo']}/releases"):
            match = re.fullmatch(project["release_pattern"], release["tag_name"])
            if not match or release["draft"] or release["prerelease"]:
                continue
            version = match["version"].replace("_", ".")
            rows.append({"id": version, "version": version, "line": version.split(".")[0] + ".x",
                         "at": norm_ts(release["published_at"]), "date_kind": "GitHub release publication (repository evidence)",
                         "url": release["html_url"], "archive_url": release["html_url"], "verified": True})
        return rows
    archive = read_url(project["archive"]).decode()
    versions = archive_versions(archive, project)
    if not versions:
        raise RuntimeError("No stable versions recognised in official archive. Review this project's archive rules.")
    rows = []
    for release in api.pages(f"repos/{project['repo']}/releases"):
        if release["draft"] or release["prerelease"]:
            continue
        match = re.fullmatch(project["release_pattern"], release["tag_name"])
        if match:
            version = match["version"].replace("_", ".")
            if version in versions:
                rows.append({"id": version, "version": version, "line": version.split(".")[0] + ".x",
                             "at": norm_ts(release["published_at"]), "date_kind": "GitHub release publication",
                             "url": release["html_url"], "archive_url": versions[version], "verified": True})
    # Archive versions without a GitHub publication timestamp are evidence of
    # releases, but must not acquire an invented publication date.
    dated = {r["id"] for r in rows}
    rows.extend({"id": version, "version": version, "line": version.split(".")[0] + ".x", "at": None,
                 "date_kind": "publication date unavailable", "url": url, "archive_url": url, "verified": True}
                for version, url in versions.items() if version not in dated)
    known = {r["id"] for r in rows}
    for tag in api.pages(f"repos/{project['repo']}/tags"):
        match = re.fullmatch(project["release_pattern"], tag["name"])
        if match:
            version = match["version"].replace("_", ".")
            if project.get("release_majors") and int(version.split(".")[0]) not in project["release_majors"]:
                continue
            if version not in known:
                rows.append({"id": version, "version": version, "line": version.split(".")[0] + ".x", "at": None,
                             "date_kind": "tag only, official distribution unverified", "verified": False,
                             "url": "https://github.com/" + project["repo"] + "/releases/tag/" + tag["name"], "archive_url": project["archive"]})
                known.add(version)
    return rows


def run(api, store, config, at, start, limit=None, full=False, git=True, mail=True, budget_projects=None):
    """Checkpoint each source independently. Partial samples never become full data."""
    projects = config["projects"] if budget_projects is None else [p for p in config["projects"] if p["id"] in budget_projects]
    def collect(source, fetch, sampled=False, **extra):
        print(f"Collecting {source}", flush=True)
        old = store.state.get(source, {})
        attempted_at = now()
        try:
            rows = fetch()
            finished_at = now()
            for row in rows:
                if row.get("history") == "observed":
                    observation = {"at": finished_at, "state": row["state"], "answer_id": row.get("answer_id"),
                                   "answerable": row.get("answerable", False)}
                    observations = row.setdefault("observations", [])
                    if not observations or any(observations[-1].get(k) != v for k, v in observation.items() if k != "at"):
                        observations.append(observation)
            info = dict(extra, status="partial" if limit and sampled else "complete", last_success=finished_at,
                        attempted_at=attempted_at, watermark=attempted_at, coverage_start=start, reason="Bounded live sample" if limit and sampled else "",
                        first_observed=old.get("first_observed", finished_at))
            info["excluded_actor_events"] = sum("actor" in row and not row["actor"] for row in rows)
            info["excluded_actor_events"] += sum(not event.get("actor") for row in rows for key in ("comments", "reviews") for event in row.get(key, []))
            info["scope_history"] = old.get("scope_history", [])
            if extra.get("branches") and old.get("branches") and old["branches"] != extra["branches"]:
                info["scope_history"] = info["scope_history"] + [{"at": at, "previous": old["branches"], "current": extra["branches"]}]
            store.save(source, rows, info)
        except Exception as error:
            # Provider errors are bounded and do not print raw data.
            reason = str(error) if isinstance(error, RuntimeError) else type(error).__name__ + ": source read failed"
            store.fail(source, "failed", reason[:300], attempted_at)
            print(f"  {source}: {reason[:300]}", flush=True)
    for project in projects:
        pid = project["id"]
        metadata = {}
        def meta():
            metadata.update(api.call(f"repos/{project['repo']}"))
            project["repo"] = metadata["full_name"]
            project["branch"] = metadata["default_branch"]
            return [{"id": str(metadata["id"]), "repo": metadata["full_name"], "branch": metadata["default_branch"],
                     "issues": metadata["has_issues"], "discussions": metadata["has_discussions"],
                     "aliases": sorted(set(project.get("aliases", []) + [project["repo"]]))}]
        collect(f"{pid}:metadata", meta)
        if not metadata:
            for channel in ("commits", "pulls", "issues", "discussions", "releases"):
                store.fail(f"{pid}:{channel}", "unavailable", "Repository metadata unavailable", at)
            continue
        for channel in ("pulls", "issues", "discussions"):
            source = f"{pid}:{channel}"
            capability = metadata.get("has_" + channel, True)
            if not capability:
                store.save(source, [], {"status": "disabled", "reason": "Repository feature is disabled", "last_success": at})
                continue
            old = store.state.get(source, {})
            incremental = not full and old.get("status") == "complete"
            # Partial checkpoints permit recovery after a rate limit without
            # repeating every completed nested read.
            previous = store.get(source)
            since = norm_ts((parse_ts(old.get("watermark", old["last_success"])) - timedelta(days=2)).isoformat()) if incremental else start
            def checkpoint(rows):
                store.save(source, rows, dict(old, status="partial", reason="Collection in progress or interrupted",
                           attempted_at=at, coverage_start=old.get("coverage_start", start)))
            if channel == "discussions":
                fetch = lambda: collect_discussions(api, project, config, previous, since if incremental else None, limit, checkpoint)
            else:
                fetch = lambda: collect_batched_items(api, project, config, channel, since, previous, limit, checkpoint, full and not limit)
            collect(source, fetch, sampled=True, repo_id=str(metadata["id"]))
        if git:
            collect(f"{pid}:commits", lambda: git_records(project, config, store.root / "git", start),
                    branches=[project["branch"]] + project.get("branches", []), full_identity_history=True)
        else:
            store.fail(f"{pid}:commits", "unavailable", "Git collection omitted for this run", at)
        collect(f"{pid}:releases", lambda: release_records(api, project))
    mail_source = config.get("dashboard_id", "logging") + ":mail"
    if mail and config.get("mail"):
        from .timeutil import completed_month, month_ends
        months = [completed_month(e)[0][:7] for e in month_ends(at, config["history_months"]) if completed_month(e)[0] >= start]
        if limit:
            months = months[-1:]
        old = store.state.get(mail_source, {})
        previous = [] if full or limit else store.get(mail_source)
        completed = [] if full or limit else list(old.get("coverage_months", []))
        months = sorted(set(months + [at[:7]]))
        months = [m for m in months if m not in completed or m >= old.get("last_success", at)[:7]]
        def fetch_mail():
            rows = list(previous)
            for month in months:
                print(f"  {mail_source}: reading {month}", flush=True)
                rows.extend(mail_records(config, [month]))
                completed[:] = sorted(set(completed + [month]))
                store.save(mail_source, rows, dict(old, status="partial", reason="Mail collection in progress or interrupted",
                           attempted_at=at, coverage_start=start, coverage_months=list(completed)))
            return rows
        collect(mail_source, fetch_mail, sampled=True, coverage_months=completed)
    elif config.get("mail"):
        store.fail(mail_source, "unavailable", "Mail collection omitted for this run", at)
    return store.state
