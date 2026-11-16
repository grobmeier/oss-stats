# SPDX-License-Identifier: Apache-2.0
"""Read-only GitHub transport with explicit pagination and request bounds."""
import json
import subprocess
import time


class GitHub:
    def __init__(self, budget=10000):
        self.budget = budget
        self.requests = 0

    def call(self, endpoint, query=None, variables=None):
        self.requests += 1
        if self.requests > self.budget:
            raise RuntimeError("Request budget exhausted. Resume with a larger budget or a narrower sample.")
        command = ["gh", "api", endpoint]
        payload = None
        if query:
            command += ["--input", "-"]
            payload = json.dumps({"query": query, "variables": variables or {}})
        else:
            command += ["--method", "GET"]
        for pause in (0, 2, 8):
            if pause:
                time.sleep(pause)
            result = subprocess.run(command, input=payload, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                body = json.loads(result.stdout)
                if isinstance(body, dict) and body.get("errors"):
                    raise RuntimeError("GitHub GraphQL: " + body["errors"][0]["message"])
                return body.get("data") if query else body
            if not any(code in result.stderr for code in ("HTTP 502", "HTTP 503", "HTTP 504", "timeout")):
                break
        # Do not emit credentials, full commands, or provider response bodies.
        raise RuntimeError(f"GitHub read failed for {endpoint.split('?')[0]}. Check authentication, permissions, or rate limits.")

    def pages(self, endpoint, limit=None):
        rows = []
        page = 1
        while True:
            separator = "&" if "?" in endpoint else "?"
            batch = self.call(f"{endpoint}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError("GitHub returned an unexpected collection shape")
            rows.extend(batch)
            if limit and len(rows) >= limit:
                return rows[:limit]
            if len(batch) < 100:
                return rows
            page += 1

    def connection(self, query, variables, select, limit=None):
        cursor, rows = None, []
        seen = set()
        while True:
            connection = select(self.call("graphql", query, dict(variables, cursor=cursor)))
            rows.extend(connection["nodes"])
            if limit and len(rows) >= limit:
                return rows[:limit]
            info = connection["pageInfo"]
            if not info["hasNextPage"]:
                return rows
            cursor = info["endCursor"]
            if not cursor or cursor in seen:
                raise RuntimeError("GitHub pagination stopped advancing")
            seen.add(cursor)


ACTOR = "author { login ... on User { id } ... on Bot { id } __typename }"
PAGE = "pageInfo { hasNextPage endCursor }"
DISCUSSIONS = """query($owner:String!,$name:String!,$cursor:String){
 repository(owner:$owner,name:$name){discussions(first:10,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC}){
 nodes { id number title url createdAt updatedAt closed closedAt
 category { name isAnswerable } answerChosenAt answer { id }
 ACTOR comments(first:30){nodes{id createdAt ACTOR replies(first:30){nodes{id createdAt ACTOR} PAGE}} PAGE}
 } PAGE } } }""".replace("ACTOR", ACTOR).replace("PAGE", PAGE)
COMMENTS = """query($id:ID!,$cursor:String){node(id:$id){... on Discussion {
 comments(first:100,after:$cursor){nodes {id createdAt ACTOR replies(first:30){nodes{id createdAt ACTOR} PAGE}} PAGE}}}}""".replace("ACTOR", ACTOR).replace("PAGE", PAGE)
REPLIES = """query($id:ID!,$cursor:String){node(id:$id){... on DiscussionComment {
 replies(first:100,after:$cursor){nodes {id createdAt ACTOR} PAGE}}}}""".replace("ACTOR", ACTOR).replace("PAGE", PAGE)


def item_query(kind, nested=None, open_only=False):
    """Batch initial connections, then page every overflowing connection."""
    pull = kind == "pulls"
    typename = "PullRequest" if pull else "Issue"
    types = ["CLOSED_EVENT", "REOPENED_EVENT", "CONVERTED_TO_DISCUSSION_EVENT"]
    fragments = ["ClosedEvent", "ReopenedEvent", "ConvertedToDiscussionEvent"]
    if pull:
        types += ["MERGED_EVENT", "READY_FOR_REVIEW_EVENT", "CONVERT_TO_DRAFT_EVENT"]
        fragments += ["MergedEvent", "ReadyForReviewEvent", "ConvertToDraftEvent"]
    timeline = " ".join(f"... on {name} {{id createdAt}}" for name in fragments)
    connections = {
        "comments": f"comments(first:100,after:CURSOR){{nodes{{id createdAt {ACTOR}}} {PAGE}}}",
        "timelineItems": f"timelineItems(first:100,after:CURSOR,itemTypes:[{','.join(types)}]){{nodes{{__typename {timeline}}} {PAGE}}}",
    }
    if pull:
        connections.update(reviews=f"reviews(first:100,after:CURSOR){{nodes{{id submittedAt {ACTOR}}} {PAGE}}}",
                           files=f"files(first:100,after:CURSOR){{totalCount nodes{{path}} {PAGE}}}")
    if nested:
        fields = connections[nested].replace("CURSOR", "$cursor")
        return "query($id:ID!,$cursor:String){node(id:$id){... on " + typename + "{" + fields + "}}}"
    fields = " ".join(value.replace("CURSOR", "null") for value in connections.values())
    extra = "isDraft mergedAt" if pull else ""
    collection = "pullRequests" if pull else "issues"
    states = "[OPEN]" if open_only else "[OPEN,CLOSED,MERGED]" if pull else "[OPEN,CLOSED]"
    return ("query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){"
            + collection + "(first:50,after:$cursor,states:" + states + ",orderBy:{field:UPDATED_AT,direction:DESC}){"
            + "nodes{id number title url createdAt updatedAt closedAt state " + ACTOR + " " + extra + " " + fields + "} " + PAGE + "}}}")
