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
from oss_stats.metrics import calculate, readiness, state_at
from oss_stats.timeutil import norm_ts

START, END = "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"


def item(**changes):
    row = {"id": "one", "actor": "human", "created_at": START, "state": "open", "history": "events", "draft": False, "events": [], "comments": [], "reviews": []}
    return dict(row, **changes)


def test_reopened_issue_history_and_half_open_boundary():
    row = item(events=[{"id": "1", "kind": "closed", "at": "2026-01-10T00:00:00Z"}, {"id": "2", "kind": "reopened", "at": END}])
    assert state_at(row, END)["state"] == "closed"
    assert state_at(row, "2026-02-02T00:00:00Z")["state"] == "open"
    result = calculate({"issues": [row]}, START, END)
    assert result["issues_closed"]["value"] == 1 and result["issues_reopened"]["value"] == 0


def test_pr_readiness_and_unreviewed_cohort():
    ready = "2026-01-12T00:00:00Z"
    row = item(events=[{"id": "1", "kind": "ready_for_review", "at": ready}], reviews=[{"actor": "other", "at": "2026-01-13T00:00:00Z"}])
    assert readiness(row) == ready
    assert state_at(row, "2026-01-05T00:00:00Z")["draft"]
    result = calculate({"pulls": [row, item(id="waiting")]}, START, END)
    assert result["pr_unreviewed"]["value"] == 1
    assert result["first_review_hours"]["value"] is None
    assert result["first_review_hours"]["n"] == 1


def test_quarterly_unique_people_and_median_recompute():
    rows = [item(id=str(n), actor="same", created_at=f"2026-0{n}-01T00:00:00Z", comments=[{"actor": "other", "at": f"2026-0{n}-02T00:00:00Z"}]) for n in (1, 2, 3)]
    report = calculate({"issues": rows}, START, "2026-04-01T00:00:00Z", floor=1)
    assert report["issue_participants"]["value"] == 2
    assert report["issue_reply_hours"]["value"] == 24


def test_self_and_bot_comments_are_not_responses():
    row = item(comments=[{"actor": "human", "at": START}, {"actor": None, "at": START}])
    result = calculate({"issues": [row]}, START, END)
    assert result["issue_unanswered"]["value"] == 1


def test_automated_submissions_count_as_work_without_inflating_people():
    result = calculate({"issues": [item(actor=None)]}, START, END)
    assert result["issues_opened"]["value"] == 1
    assert result["issue_backlog"]["value"] == 1
    assert result["issue_participants"]["value"] == 0


def test_answer_removal_only_changes_observed_future():
    row = item(history="observed", observations=[{"at": "2026-01-10T00:00:00Z", "state": "open", "answerable": True, "answer_id": "answer"},
                                                {"at": "2026-02-10T00:00:00Z", "state": "open", "answerable": True, "answer_id": None}])
    assert state_at(row, "2026-01-05T00:00:00Z") is None
    assert state_at(row, END)["answer_id"] == "answer"
    assert state_at(row, "2026-03-01T00:00:00Z")["answer_id"] is None


def test_retention_excludes_immature_cohorts():
    result = calculate({"commits": [{"id": "1", "actor": "new", "at": START}]}, START, END)
    assert result["retention"]["n"] == 0


def test_conversion_closes_historical_issue():
    row = item(events=[{"id": "1", "at": "2026-01-20T00:00:00Z", "kind": "converted_to_discussion"}])
    assert state_at(row, END)["state"] == "closed"


def test_utc_normalisation():
    assert norm_ts("2026-01-01T01:00:00+01:00") == START
