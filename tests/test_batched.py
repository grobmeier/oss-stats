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
import pytest

from oss_stats.collect import collect_batched_items, collect_discussions
from oss_stats.config import load
from oss_stats.github import item_query


def connection(rows, more=False):
    return {"nodes": rows, "pageInfo": {"hasNextPage": more, "endCursor": "next" if more else None}}


def test_batch_expands_nested_comments_and_reconciles_deletions():
    class API:
        def call(self, endpoint, query, variables):
            if "id" in variables:
                return {"node": {"comments": connection([{"id": "c2", "createdAt": "2026-01-03T00:00:00Z", "author": {"id": "U2", "login": "other"}}])}}
            return {"repository": {"issues": connection([{
                "id": "i1", "number": 1, "title": "Issue", "url": "https://github.com/a/b/issues/1", "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-03T00:00:00Z", "closedAt": None, "state": "OPEN", "author": {"id": "U1", "login": "first"},
                "comments": connection([{"id": "c1", "createdAt": "2026-01-02T00:00:00Z", "author": None}], True),
                "timelineItems": connection([])}])}}
    rows = collect_batched_items(API(), {"repo": "a/b"}, load(), "issues", "2020-01-01T00:00:00Z", previous=[{"id": "deleted"}], full=True)
    assert [r["id"] for r in rows] == ["i1"]
    assert len(rows[0]["comments"]) == 2
    assert rows[0]["comments"][1]["actor"] == "github:U2"


def test_discussion_replies_and_observation_history_survive_refresh():
    class API:
        def connection(self, query, variables, select, limit=None):
            if "owner" in variables:
                return [{"id": "d1", "number": 1, "title": "Question", "url": "https://github.com/a/b/discussions/1", "createdAt": "2026-01-01T00:00:00Z",
                         "updatedAt": "2026-01-03T00:00:00Z", "closed": False, "closedAt": None, "author": {"id": "U1", "login": "first"},
                         "category": {"name": "Q&A", "isAnswerable": True}, "answer": None, "answerChosenAt": None}]
            if variables["id"] == "d1":
                return [{"id": "c1", "createdAt": "2026-01-02T00:00:00Z", "author": None}]
            return [{"id": "reply", "createdAt": "2026-01-03T00:00:00Z", "author": {"id": "U2", "login": "second"}}]
    rows = collect_discussions(API(), {"repo": "a/b"}, load(), previous=[{"id": "d1", "observations": [{"at": "2026-01-02T00:00:00Z", "answer_id": "old"}]}])
    assert rows[0]["observations"][0]["answer_id"] == "old"
    assert rows[0]["comments"][-1]["actor"] == "github:U2"


@pytest.mark.parametrize("kind", ["issues", "pulls"])
def test_queries_are_balanced_and_include_nested_pagination(kind):
    for field in [None, "timelineItems", "comments"] + (["files", "reviews"] if kind == "pulls" else []):
        query = item_query(kind, field)
        assert query.count("{") == query.count("}")
        assert "pageInfo" in query and "$cursor" in query
