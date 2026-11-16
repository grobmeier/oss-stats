import json

import pytest

from logging_stats.collect import actor, archive_versions, collect_discussions, collect_items, normal_event, parse_mbox
from logging_stats.config import email_identity, load, modules
from logging_stats.github import GitHub


def test_rest_pagination_reaches_later_pages():
    class API(GitHub):
        def call(self, endpoint, **kwargs):
            return [{"id": n} for n in range(100)] if endpoint.endswith("&page=1") else [{"id": 100}]
    assert len(API().pages("repos/apache/example/issues")) == 101


def test_graphql_pagination_reaches_nested_pages():
    class API(GitHub):
        def call(self, endpoint, query, variables):
            return {"nodes": [variables["cursor"] or "first"], "pageInfo": {
                "hasNextPage": variables["cursor"] is None, "endCursor": "second"}}
    assert API().connection("query", {}, lambda d: d) == ["first", "second"]


def test_issue_index_excludes_pull_requests():
    class API:
        def pages(self, endpoint, limit=None):
            if "comments" in endpoint or "timeline" in endpoint or "state=open" in endpoint:
                return []
            return [{"node_id": "issue", "number": 1, "title": "Issue", "html_url": "https://github.com/a/b/issues/1",
                     "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z", "state": "open", "user": {"id": 1, "login": "human"}},
                    {"node_id": "pull", "pull_request": {}, "number": 2}]
    # Presence, rather than truthiness, identifies a PR in a REST issue object.
    api = API()
    rows = collect_items(api, {"repo": "a/b"}, load(), "issues", "2020-01-01T00:00:00Z")
    assert [r["id"] for r in rows] == ["issue"]


def test_mail_parsing_uses_references_and_stores_no_body():
    raw = b'From sender Mon Nov 1 00:00:00 2026\nMessage-ID: <one>\nDate: Sun, 1 Nov 2026 00:00:00 +0000\nFrom: Person <person@example.com>\n\nSECRET BODY\nFrom reply Mon Nov 2 00:00:00 2026\nMessage-ID: <two>\nReferences: <one>\nDate: Mon, 2 Nov 2026 00:00:00 +0000\nFrom: Other <other@example.com>\n\nOTHER BODY\n'
    rows = parse_mbox(raw, load())
    assert len(rows) == 2 and rows[1]["root"] == "<one>"
    assert "BODY" not in json.dumps(rows) and "person@example.com" not in json.dumps(rows)


def test_archive_rules_recognise_each_project():
    for project in load()["projects"]:
        versions = archive_versions('<a href="2.3.4/">2.3.4/</a><a href="2.3.5-rc1/">rc</a>', project)
        assert list(versions) == ["2.3.4"]


def test_inactive_log4j1_releases_do_not_enter_the_active_project():
    project = load()["projects"][0]
    versions = archive_versions('<a href="1.2.17/">old</a><a href="2.25.3/">current</a>', project)
    assert list(versions) == ["2.25.3"]


def test_bots_and_stable_ids():
    assert actor({"id": 12, "node_id": "U_12", "login": "person"}, load()) == "github:U_12"
    assert actor({"id": 12, "login": "renovate[bot]"}, load()) is None


def test_reviewed_email_aliases_join_without_using_display_names():
    config = load()
    config["identity_aliases"] = {"old@example.com": "canonical@example.com"}
    assert email_identity("OLD@example.com", config) == email_identity("canonical@example.com", config)
    assert email_identity("different@example.com", config) != email_identity("canonical@example.com", config)


def test_modules_overlap_without_duplicate_labels():
    project = load()["projects"][0]
    assert modules(["log4j-api/A", "log4j-api/B", "log4j-core/C"], project) == ["API", "Core"]


def test_conversion_event_retains_provenance():
    assert normal_event({"id": 4, "event": "converted_to_discussion", "created_at": "2026-01-01T00:00:00Z"})["kind"] == "converted_to_discussion"


def test_mail_error_document_does_not_become_empty_success():
    with pytest.raises(RuntimeError, match="error document"):
        parse_mbox(b'{"error":"mailbox unavailable"}', load())
