# SPDX-License-Identifier: Apache-2.0
"""First-observed PR cohorts with fixed, fully observed outcome windows."""
from datetime import timedelta

from .timeutil import norm_ts, parse_ts


def calculate_journey(pulls, start, end, observed_until, add):
    people = {}
    for row in pulls:
        if row.get("actor") and row["created_at"] < observed_until:
            people.setdefault(row["actor"], []).append(row)
    for rows in people.values():
        rows.sort(key=lambda r: (r["created_at"], r["id"]))
    cohort = [rows for rows in people.values() if start <= rows[0]["created_at"] < end]
    add("newcomer_pr_authors", len(cohort))
    for days, prefix in ((30, "response"), (90, "followup")):
        eligible = []
        for rows in cohort:
            deadline = norm_ts((parse_ts(rows[0]["created_at"]) + timedelta(days=days)).isoformat())
            if deadline < observed_until:
                eligible.append((rows, deadline))
        add("newcomer_" + prefix + "_eligible", len(eligible))
        if days == 30:
            responded = sum(any(c.get("actor") and c["actor"] != rows[0]["actor"]
                                and rows[0]["created_at"] <= c["at"] <= deadline
                                for kind in ("comments", "reviews") for c in rows[0].get(kind, []))
                            for rows, deadline in eligible)
            outcomes = [("responded", "response", responded)]
        else:
            merged = sum(bool(rows[0].get("merged_at") and rows[0]["created_at"] <= rows[0]["merged_at"] <= deadline)
                         for rows, deadline in eligible)
            returned = sum(any(r["created_at"] <= deadline for r in rows[1:]) for rows, deadline in eligible)
            outcomes = [("merged", "merge", merged), ("returned", "return", returned)]
        for count_name, rate_name, count in outcomes:
            add("newcomer_" + count_name, count)
            add("newcomer_" + rate_name + "_share", count / len(eligible) if eligible else 0,
                len(eligible), "rate", None if eligible else "No cohort members have a fully observed outcome window")
