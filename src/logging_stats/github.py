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
 repository(owner:$owner,name:$name){discussions(first:50,after:$cursor,orderBy:{field:UPDATED_AT,direction:DESC}){
 nodes { id number title url createdAt updatedAt closed closedAt
 category { name isAnswerable } answerChosenAt answer { id }
 ACTOR } PAGE } } }""".replace("ACTOR", ACTOR).replace("PAGE", PAGE)
COMMENTS = """query($id:ID!,$cursor:String){node(id:$id){... on Discussion {
 comments(first:100,after:$cursor){nodes {id createdAt ACTOR} PAGE}}}}""".replace("ACTOR", ACTOR).replace("PAGE", PAGE)
REPLIES = """query($id:ID!,$cursor:String){node(id:$id){... on DiscussionComment {
 replies(first:100,after:$cursor){nodes {id createdAt ACTOR} PAGE}}}}""".replace("ACTOR", ACTOR).replace("PAGE", PAGE)
