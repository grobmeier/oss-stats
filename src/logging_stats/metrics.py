# SPDX-License-Identifier: Apache-2.0
"""Calendar metrics from events. Public output contains aggregates only."""
from collections import Counter
from datetime import timedelta
from statistics import median

from .timeutil import completed_month, days_between, hours_between, month_ends, parse_ts

DEFINITIONS = {
    "commit_authors": "Distinct human commit authors during the period. Git author identities are separate from GitHub accounts.",
    "commits": "Non-merge commits authored during the period. Commits on selected branches count once per repository and SHA.",
    "new_commit_authors": "Authors whose first in-scope commit falls in this period. Requires full selected-branch history.",
    "retention": "Share of eligible new commit authors with a second commit within 180 days. Cohorts require 180 days of observation.",
    "pr_authors": "Distinct human authors of pull requests created in this period, including drafts.",
    "reviewers": "Distinct humans who submitted a review during the period. Self-reviews and bots are excluded.",
    "reviewer_concentration": "Sum of squared shares of human review submissions. Submissions do not measure effort or quality.",
    "prs_opened": "Non-draft pull requests created in the period, plus drafts first made ready in the period.",
    "prs_closed": "Closure events without a merge during this period. Repeated closures are separate events.",
    "prs_merged": "Pull requests merged during this period.",
    "prs_reopened": "Pull-request reopening events during this period.",
    "pr_backlog": "Open, non-draft pull requests immediately before period end, reconstructed from lifecycle events.",
    "pr_age_days": "Median age since creation among open, non-draft pull requests immediately before period end.",
    "pr_aged_28": "Open, non-draft pull requests at least 28 days old at period end. This is a filter, not a service commitment.",
    "first_review_hours": "Median hours from first readiness to the first later human review from another account. Uses readiness cohorts.",
    "pr_unreviewed": "Pull requests first made ready during the period without another human's review before period end.",
    "pr_unreviewed_share": "Unreviewed share of the period's readiness cohort. Recent cohorts have less observation time.",
    "merge_hours": "Median hours from creation to merge for non-draft pull requests merged during this period.",
    "issue_participants": "Distinct human authors and commenters active on issues during this period. Pull requests are excluded.",
    "issues_opened": "Issues created during this period. Pull requests returned by the Issues API are excluded.",
    "issues_closed": "Issue closure events during this period. Closure does not establish resolution.",
    "issues_reopened": "Issue reopening events during this period.",
    "issue_backlog": "Open issues immediately before period end, reconstructed from lifecycle events.",
    "issue_age_days": "Median age since creation among issues open immediately before period end.",
    "issue_backlog_unanswered": "Open issues at period end without another human's comment before period end.",
    "issue_reply_hours": "Median time to another human's first comment for issues created in this period and answered before period end.",
    "issue_unanswered": "Issues created in this period without another human's comment before period end.",
    "issue_unanswered_share": "Unanswered share of issues created in this period. Recent cohorts have less observation time.",
    "discussion_participants": "Distinct human discussion authors, commenters, and reply authors active during the period.",
    "discussions_opened": "Discussions created during this period.",
    "discussion_comments": "Human comments and replies submitted during this period.",
    "discussion_reply_hours": "Median time to another human's first comment or reply for discussions created in this period.",
    "discussion_unanswered": "Discussions created in this period without another human's comment or reply before period end.",
    "discussion_unanswered_share": "Unanswered share of discussions created in this period. Recent cohorts have less observation time.",
    "discussion_answered": "Answer-capable discussions with a marked answer in an observed snapshot at period end. No historical inference.",
    "discussion_answered_share": "Marked-answer share among observed answer-capable discussions. An unmarked answer does not establish an unresolved question.",
    "mail_messages": "Human messages sent to the shared Logging development list during this period.",
    "mail_participants": "Distinct normalised human sender identities active during the period. No names or addresses are published.",
    "mail_threads": "Observed root messages sent during the period. Unlinked messages are not joined by subject.",
    "mail_reply_hours": "Median time from a root message to the first message by another human before period end.",
    "mail_unanswered": "Observed root messages created in this period without another human's reply before period end.",
    "mail_unanswered_share": "Unanswered share of root messages created in this period. Missing references can affect threading.",
    "stable_releases": "Archive-verified stable releases with a known publication timestamp in this period. Undated archive entries are shown separately.",
    "release_age_days": "Days since the latest dated archive-verified stable release before period end. Other release dates can be unavailable.",
}
for _name, _channel in (("new_pr_authors", "PR authors"), ("new_reviewers", "reviewers"),
                         ("new_issue_participants", "issue participants"), ("new_discussion_participants", "discussion participants"),
                         ("new_mail_participants", "mail senders")):
    DEFINITIONS[_name] = f"First observed {_channel} within stored coverage. This does not establish first-ever participation."


def in_period(at, start, end):
    return bool(at and start <= at < end)


def state_at(row, end):
    if row["created_at"] >= end:
        return None
    if row.get("history") == "observed":
        observations = [o for o in row.get("observations", []) if o["at"] < end]
        return max(observations, key=lambda o: o["at"]) if observations else None
    events = sorted(row.get("events", []), key=lambda e: (e["at"], e["id"]))
    draft_events = [e for e in events if e["kind"] in ("ready_for_review", "convert_to_draft")]
    draft = draft_events[0]["kind"] == "ready_for_review" if draft_events else row.get("draft", False)
    state = "open"
    for event in events:
        if event["at"] >= end:
            continue
        if event["kind"] in ("closed", "merged", "converted_to_discussion"):
            state = "closed"
        elif event["kind"] == "reopened":
            state = "open"
        elif event["kind"] == "ready_for_review":
            draft = False
        elif event["kind"] == "convert_to_draft":
            draft = True
    # Timestamp fields are reliable for an original closure even if its event
    # disappeared. Missing history after a reopen must stay unavailable.
    if row.get("closed_at") and row["closed_at"] < end and not events:
        state = "closed"
    return {"state": state, "draft": draft}


def readiness(row):
    events = sorted((e for e in row.get("events", []) if e["kind"] in ("ready_for_review", "convert_to_draft")), key=lambda e: e["at"])
    if events and events[0]["kind"] == "ready_for_review":
        return events[0]["at"]
    if not events and row.get("draft"):
        return None
    return row["created_at"]


def response(row, end, reviews=False):
    start = readiness(row) if reviews else row["created_at"]
    if not start:
        return None
    candidates = [c["at"] for c in row.get("reviews" if reviews else "comments", [])
                  if c.get("actor") and c["actor"] != row.get("actor") and start <= c["at"] < end]
    return min(candidates) if candidates else None


def population(rows, start, end, comments=False, reviews=False):
    people = {r["actor"] for r in rows if r.get("actor") and in_period(r.get("created_at", r.get("at")), start, end)}
    if comments or reviews:
        people.update(c["actor"] for r in rows for c in r.get("reviews" if reviews else "comments", [])
                      if c.get("actor") and in_period(c["at"], start, end) and (not reviews or c["actor"] != r.get("actor")))
    return people


def calculate(records, start, end, floor=5, stale=28):
    values = {}
    def add(name, value, n=None, statistic=None, reason=None):
        n = n if n is not None else value
        suppressed = statistic and n < floor
        values[name] = {"value": None if suppressed or reason else value, "n": n,
                        "status": "unavailable" if reason else "insufficient data" if suppressed else "complete",
                        "reason": reason or ""}
    commits = [r for r in records.get("commits", []) if r.get("actor")]
    add("commits", sum(in_period(r["at"], start, end) for r in commits))
    add("commit_authors", len(population(commits, start, end)))
    authors = {}
    for row in commits:
        authors.setdefault(row["actor"], []).append(row["at"])
    for dates in authors.values():
        dates.sort()
    add("new_commit_authors", sum(start <= dates[0] < end for dates in authors.values()))
    eligible = [dates for dates in authors.values() if (parse_ts(end) - parse_ts(dates[0])).days >= 180]
    retained = sum(len(dates) > 1 and days_between(dates[0], dates[1]) <= 180 for dates in eligible)
    add("retention", retained / len(eligible) if eligible else 0, len(eligible), "rate")
    pulls = records.get("pulls", [])
    add("pr_authors", len(population(pulls, start, end)))
    def newcomers(name, observations):
        first = {}
        for person, at in observations:
            if person and at and (person not in first or at < first[person]):
                first[person] = at
        add(name, sum(in_period(at, start, end) for at in first.values()))
    newcomers("new_pr_authors", [(r.get("actor"), r["created_at"]) for r in pulls])
    newcomers("new_reviewers", [(c.get("actor"), c["at"]) for r in pulls for c in r.get("reviews", []) if c.get("actor") != r.get("actor")])
    reviews = [c for r in pulls for c in r.get("reviews", []) if c.get("actor") and c["actor"] != r.get("actor") and in_period(c["at"], start, end)]
    shares = Counter(c["actor"] for c in reviews)
    add("reviewers", len(shares))
    add("reviewer_concentration", sum((v / len(reviews)) ** 2 for v in shares.values()) if reviews else 0, len(shares), "concentration")
    for kind, prefix in (("pulls", "pr"), ("issues", "issue"), ("discussions", "discussion")):
        rows = records.get(kind, [])
        human = [r for r in rows if r.get("actor")]
        cohort = [r for r in human if in_period(readiness(r) if kind == "pulls" else r["created_at"], start, end)]
        plural = {"pulls": "prs", "issues": "issues", "discussions": "discussions"}[kind]
        add(plural + "_opened", len(cohort))
        if kind != "pulls":
            add(prefix + "_participants", len(population(rows, start, end, comments=True)))
            newcomers("new_" + prefix + "_participants", [(r.get("actor"), r["created_at"]) for r in rows] + [(c.get("actor"), c["at"]) for r in rows for c in r.get("comments", [])])
        latencies = [hours_between(readiness(r) if kind == "pulls" else r["created_at"], reply)
                     for r in cohort if (reply := response(r, end, kind == "pulls"))]
        unanswered = len(cohort) - len(latencies)
        add("first_review_hours" if kind == "pulls" else prefix + "_reply_hours", median(latencies) if latencies else 0, len(latencies), "median")
        add(prefix + ("_unreviewed" if kind == "pulls" else "_unanswered"), unanswered)
        add(prefix + ("_unreviewed_share" if kind == "pulls" else "_unanswered_share"), unanswered / len(cohort) if cohort else 0, len(cohort), "rate")
        if kind != "discussions":
            for event, suffix in (("closed", "closed"), ("reopened", "reopened")):
                add(plural + "_" + suffix, sum(in_period(e["at"], start, end) and e["kind"] == event
                    and not (kind == "pulls" and r.get("merged_at") == e["at"])
                    for r in rows for e in r.get("events", [])))
            backlog = [r for r in rows if (s := state_at(r, end)) and s["state"] == "open" and not s.get("draft")]
            add(prefix + "_backlog", len(backlog))
            ages = [days_between(r["created_at"], end) for r in backlog]
            add(prefix + "_age_days", median(ages) if ages else 0, len(ages), "median")
            if kind == "pulls":
                add("pr_aged_28", sum(age >= stale for age in ages))
            else:
                add("issue_backlog_unanswered", sum(not response(r, end) for r in backlog))
        else:
            add("discussion_comments", sum(c.get("actor") is not None and in_period(c["at"], start, end) for r in rows for c in r.get("comments", [])))
            observed = [(r, s) for r in rows if (s := state_at(r, end)) and s.get("answerable")]
            answered = sum(bool(s.get("answer_id")) for _, s in observed)
            reason = None if observed else "Answer history is available only from observed snapshots onward"
            add("discussion_answered", answered, len(observed), reason=reason)
            add("discussion_answered_share", answered / len(observed) if observed else 0, len(observed), "rate", reason)
    merged = [r for r in pulls if in_period(r.get("merged_at"), start, end) and not r.get("draft")]
    add("prs_merged", len(merged))
    latencies = [hours_between(r["created_at"], r["merged_at"]) for r in merged]
    add("merge_hours", median(latencies) if latencies else 0, len(latencies), "median")
    releases = records.get("releases", [])
    add("stable_releases", sum(in_period(r.get("at"), start, end) and r.get("verified", False) for r in releases))
    dated = [r for r in releases if r.get("at") and r["at"] < end and r.get("verified")]
    add("release_age_days", min(days_between(r["at"], end) for r in dated) if dated else 0, len(dated), reason=None if dated else "No verified publication timestamp")
    undated = [r for r in releases if not r.get("at") and r.get("verified")]
    if undated:
        values["stable_releases"].update(status="partial", reason=f"{len(undated)} archive releases have no publication timestamp. Their periods are unknown.")
        if not dated:
            values["stable_releases"].update(value=None, status="unavailable")
        def version_key(row):
            return tuple(int(part) for part in row["version"].split("."))
        if dated and max(map(version_key, undated)) > max(map(version_key, dated)):
            values["release_age_days"].update(value=None, status="unavailable", reason="A newer verified version has no publication timestamp")
    messages = [r for r in records.get("mail", []) if r.get("actor")]
    add("mail_messages", sum(in_period(r["at"], start, end) for r in messages))
    add("mail_participants", len(population(messages, start, end)))
    newcomers("new_mail_participants", [(r["actor"], r["at"]) for r in messages])
    roots = [r for r in messages if r["root"] == r["id"] and in_period(r["at"], start, end)]
    add("mail_threads", len(roots))
    replies = []
    for root in roots:
        dates = [r["at"] for r in messages if r["root"] == root["id"] and r["actor"] != root["actor"] and root["at"] <= r["at"] < end]
        if dates:
            replies.append(hours_between(root["at"], min(dates)))
    add("mail_reply_hours", median(replies) if replies else 0, len(replies), "median")
    add("mail_unanswered", len(roots) - len(replies))
    add("mail_unanswered_share", (len(roots) - len(replies)) / len(roots) if roots else 0, len(roots), "rate")
    return values


def channel(metric):
    if metric.startswith("new_") and metric != "new_commit_authors":
        return channel(metric[4:])
    if metric.startswith("mail_"):
        return "mail"
    if metric.startswith(("issue",)):
        return "issues"
    if metric.startswith("discussion"):
        return "discussions"
    if metric.startswith(("stable_", "release_")):
        return "releases"
    if metric in ("commits", "commit_authors", "new_commit_authors", "retention"):
        return "commits"
    return "pulls"


def windows(at, count):
    monthly = [(completed_month(end)[0], end, "monthly") for end in month_ends(at, count)]
    quarters = []
    for start, end, _ in monthly:
        if int(start[5:7]) in (1, 4, 7, 10):
            date = parse_ts(start)
            month = date.month + 3
            finish = date.replace(year=date.year + (month > 12), month=(month - 1) % 12 + 1).strftime("%Y-%m-%dT%H:%M:%SZ")
            if finish <= at:
                quarters.append((start, finish, "quarterly"))
    current_start = at[:7] + "-01T00:00:00Z"
    return monthly + quarters + [(current_start, at, "partial month")]


def build_report(store, config, at):
    report = {"schema_version": 1, "definition_version": config["definition_version"], "as_of": at,
              "title": config["title"], "target_url": config["target_url"], "projects": config["projects"],
              "inactive": config["inactive"], "metrics": [], "waiting": {}, "sources": {}, "releases": {},
              "definitions": DEFINITIONS, "provenance": {"author": "Russell Spitzer", "url": "https://github.com/RussellSpitzer/iceberg-community-health",
              "revision": "5e26873783da1849343a7c3dd0403f9ef56240d4"}}
    for source, info in store.state.items():
        report["sources"][source] = {k: v for k, v in info.items() if k not in ("snapshot", "digest")}
    expected = [f"{p['id']}:{kind}" for p in config["projects"] for kind in ("metadata", "commits", "pulls", "issues", "discussions", "releases")] + ["logging:mail"]
    for source in expected:
        report["sources"].setdefault(source, {"status": "unavailable", "reason": "Not collected"})
    all_records = {kind: [] for kind in ("commits", "pulls", "issues", "discussions", "releases")}
    selections = []
    for project in config["projects"]:
        pid = project["id"]
        records = {kind: store.get(f"{pid}:{kind}") for kind in all_records}
        for kind, rows in records.items():
            all_records[kind].extend(dict(r, id=f"{pid}:{r['id']}") for r in rows)
        selections.append((pid, records))
        for module in project.get("modules", {}):
            subset = {kind: [r for r in records[kind] if module in r.get("modules", [])] for kind in ("commits", "pulls")}
            selections.append((pid + "/" + module, subset))
        report["releases"][pid] = records["releases"]
        waiting = []
        for kind in ("pulls", "issues", "discussions"):
            for row in records[kind]:
                state = state_at(row, at)
                # Include observations taken at this run's exact timestamp.
                if row.get("history") == "observed":
                    state = row.get("observations", [{}])[-1]
                if state and state.get("state") == "open" and not state.get("draft") and not response(row, at, kind == "pulls"):
                    waiting.append({"title": row["title"], "url": row["url"], "kind": kind,
                                    "age_days": round(days_between(row["created_at"], at)),
                                    "updated_at": row["updated_at"], "reason": "Awaiting another human's review" if kind == "pulls" else "No other human response"})
        report["waiting"][pid] = sorted(waiting, key=lambda r: -r["age_days"])[:50]
    selections.append(("logging", all_records))
    selections.append(("shared-list", {"mail": store.get("logging:mail")}))
    for scope, records in selections:
        for start, end, grouping in windows(at, config["history_months"]):
            values = calculate(records, start, end, config["sample_floor"], config["stale_days"])
            for name, result in values.items():
                kind = channel(name)
                if scope == "shared-list" and kind != "mail" or scope != "shared-list" and kind == "mail":
                    continue
                if "/" in scope and kind not in ("commits", "pulls"):
                    continue
                sources = [report["sources"].get(f"{p['id']}:{kind}", {}) for p in config["projects"]] if scope == "logging" else [report["sources"].get("logging:mail" if scope == "shared-list" else scope.split("/")[0] + ":" + kind, {})]
                source_statuses = {s.get("status", "unavailable") for s in sources}
                unavailable = source_statuses <= {"disabled", "unavailable", "failed"}
                if unavailable:
                    result.update(value=None, status="disabled" if source_statuses == {"disabled"} else "unavailable", reason="Source coverage is unavailable. See Coverage.")
                elif source_statuses != {"complete"}:
                    result.update(status="partial" if result["value"] is not None else result["status"], reason="Incomplete source coverage. See Coverage.")
                coverage = [s.get("coverage_start") for s in sources if s.get("coverage_start")]
                if coverage and start < max(coverage) and kind != "commits":
                    result.update(value=None, status="unavailable", reason="Period starts before declared source coverage")
                report["metrics"].append(dict(result, metric=name, scope=scope, start=start, end=end, grouping=grouping))
    return report
