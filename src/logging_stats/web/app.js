/* SPDX-License-Identifier: Apache-2.0 */
"use strict";
const $ = (id) => document.getElementById(id);
const node = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
const link = (title, url) => {
  const n = node("a", title);
  if (/^(https:\/\/|\.\/|#)/.test(url)) n.href = url;
  return n;
};
const label = (name) =>
  name
    .replaceAll("_", " ")
    .replace(/\bpr\b/g, "PR")
    .replace(/\bprs\b/g, "PRs")
    .replace(/^./, (c) => c.toUpperCase());
function value(row) {
  if (!row || row.value === null) return "—";
  const n = row.value;
  return /share|retention/.test(row.metric)
    ? (n * 100).toFixed(1) + "%"
    : Number.isInteger(n)
      ? n.toLocaleString()
      : n.toFixed(1);
}
function table(headers, rows, caption) {
  const wrap = node("div", undefined, "table-wrap"),
    t = node("table");
  if (caption) t.append(node("caption", caption));
  const head = node("thead"),
    tr = node("tr");
  headers.forEach((h) => {
    const th = node("th", h);
    th.scope = "col";
    tr.append(th);
  });
  head.append(tr);
  t.append(head);
  const body = node("tbody");
  rows.forEach((row) => {
    const tr = node("tr");
    row.forEach((cell) => {
      const td = node("td");
      td.append(
        cell instanceof Node ? cell : document.createTextNode(String(cell)),
      );
      tr.append(td);
    });
    body.append(tr);
  });
  t.append(body);
  wrap.append(t);
  return wrap;
}
function section(title) {
  const n = node("section");
  n.append(node("h2", title));
  return n;
}
fetch("./metrics.json")
  .then((r) => {
    if (!r.ok) throw Error("Report could not be loaded");
    return r.json();
  })
  .then(start)
  .catch((e) => {
    $("freshness").textContent = e.message;
  });
function start(report) {
  const scope = document.body.dataset.scope,
    project = report.projects.find((p) => p.id === scope);
  $("freshness").textContent =
    `Report ${report.as_of.replace("T", " ").replace("Z", " UTC")} · Definitions ${report.definition_version}`;
  if (project?.status) {
    const n = node("p", project.status, "notice");
    n.append(" ", link("Status source", project.status_url));
    $("warning").append(n);
  }
  const incomplete = Object.entries(report.sources).filter(
    ([key, s]) =>
      (scope === "logging" ||
        key.startsWith(scope + ":") ||
        key === "logging:mail") &&
      !["complete", "disabled"].includes(s.status),
  );
  if (incomplete.length) {
    const warning = node("div", undefined, "notice");
    warning.append(
      node(
        "p",
        `${incomplete.length} sources have incomplete coverage. Partial values describe only collected records.`,
      ),
    );
    const detail = node("details");
    detail.append(
      node("summary", "Show affected sources"),
      node(
        "p",
        incomplete.map(([key, s]) => key + " (" + s.status + ")").join(", "),
      ),
    );
    warning.append(detail, link("Inspect coverage", "#coverage"));
    $("warning").append(warning);
  }
  if (project?.modules) {
    $("module-label").hidden = false;
    Object.keys(project.modules).forEach((m) => {
      const o = node("option", m);
      o.value = m;
      $("module").append(o);
    });
  }
  Object.entries(report.definitions).forEach(([key, text]) => {
    $("definitions").append(node("dt", label(key)), node("dd", text));
  });
  const sources = Object.entries(report.sources).filter(
    ([key]) =>
      scope === "logging" ||
      key.startsWith(scope + ":") ||
      key === "logging:mail",
  );
  if (sources.some(([, s]) => s.scope_history?.length)) {
    $("warning").append(
      node(
        "p",
        "Selected branch scope changed. Comparisons use the current branch scope. Inspect Coverage before comparing older reports.",
        "notice",
      ),
    );
  }
  $("sources").append(
    table(
      ["Source", "State", "Records", "Last success / UTC", "Coverage / notes"],
      sources.map(([key, s]) => [
        key,
        s.status,
        s.records ?? "—",
        s.last_success ?? "Never",
        `${s.coverage_start || "Observed only"} ${s.reason || ""} ${s.branches ? "Branches: " + s.branches.join(", ") : ""} ${s.excluded_actor_events ? "Excluded bot or unavailable actor events: " + s.excluded_actor_events : ""}`,
      ]),
    ),
  );
  const dates = [
    ...new Set(
      report.metrics
        .filter((r) => r.grouping === "monthly")
        .map((r) => r.start.slice(0, 7)),
    ),
  ].sort();
  const latest = dates.at(-1);
  $("to").value = latest;
  function setRange() {
    const n = Number($("range").value);
    $("from").value = dates[Math.max(0, dates.length - n)];
    $("to").value = latest;
  }
  setRange();
  $("range").addEventListener("change", () => {
    setRange();
    render();
  });
  ["from", "to", "group", "module"].forEach((id) =>
    $(id).addEventListener("change", render),
  );
  $("filters").addEventListener("submit", (e) => e.preventDefault());
  function render() {
    const root = $("dashboard");
    root.replaceChildren();
    const selected = scope + ($("module").value ? "/" + $("module").value : "");
    const grouping = $("group").value;
    const filtered = report.metrics.filter(
      (r) =>
        r.scope === selected &&
        r.grouping === grouping &&
        (grouping === "partial month" ||
          (r.start.slice(0, 7) >= $("from").value &&
            r.start.slice(0, 7) <= $("to").value)),
    );
    if (!filtered.length) {
      root.append(node("p", "No periods match this range."));
      return;
    }
    const end = filtered
        .map((r) => r.end)
        .sort()
        .at(-1),
      current = filtered.filter((r) => r.end === end);
    const find = (name, rows = current) => rows.find((r) => r.metric === name);
    root.append(
      node(
        "p",
        `Cards show ${current[0].start.slice(0, 10)} to ${end.slice(0, 10)} (end excluded). Trends show each selected period separately.`,
        "scope-note",
      ),
    );
    if (scope === "logging") {
      const s = section("Across the projects");
      s.append(
        table(
          ["Project", "Commit authors", "Open PRs", "Open issues", "Coverage"],
          report.projects.map((p) => {
            const rows = report.metrics.filter(
              (r) =>
                r.scope === p.id && r.end === end && r.grouping === grouping,
            );
            const name = node("span");
            name.append(link(p.name, "./" + p.id + ".html"));
            if (p.status)
              name.append(node("small", " · Dormant / under rework"));
            return [
              name,
              value(find("commit_authors", rows)),
              value(find("pr_backlog", rows)),
              value(find("issue_backlog", rows)),
              Object.entries(report.sources)
                .filter(([key]) => key.startsWith(p.id + ":"))
                .map(([, v]) => v.status)
                .filter((v, i, a) => a.indexOf(v) === i)
                .join(", "),
            ];
          }),
          "Project headcounts overlap. The overview uses distinct identities within each channel.",
        ),
      );
      root.append(s);
    }
    const groups = [
      [
        "Contributions",
        [
          "commits",
          "commit_authors",
          "new_commit_authors",
          "retention",
          "pr_authors",
          "new_pr_authors",
          "reviewers",
          "new_reviewers",
          "reviewer_concentration",
        ],
      ],
      [
        "Pull requests",
        [
          "prs_opened",
          "prs_merged",
          "prs_closed",
          "prs_reopened",
          "pr_backlog",
          "pr_age_days",
          "pr_aged_28",
          "first_review_hours",
          "pr_unreviewed",
          "pr_unreviewed_share",
          "merge_hours",
        ],
      ],
      [
        "Issues",
        [
          "issues_opened",
          "issues_closed",
          "issues_reopened",
          "issue_participants",
          "new_issue_participants",
          "issue_backlog",
          "issue_age_days",
          "issue_backlog_unanswered",
          "issue_reply_hours",
          "issue_unanswered",
          "issue_unanswered_share",
        ],
      ],
      [
        "Discussions",
        [
          "discussions_opened",
          "discussion_participants",
          "new_discussion_participants",
          "discussion_comments",
          "discussion_reply_hours",
          "discussion_unanswered",
          "discussion_unanswered_share",
          "discussion_answered",
          "discussion_answered_share",
        ],
      ],
      ["Releases", ["stable_releases", "release_age_days"]],
    ];
    for (const [title, ids] of groups) {
      const s = section(title),
        cards = node("div", undefined, "cards");
      for (const id of ids) {
        const row = find(id);
        if (!row) continue;
        const card = node("div", undefined, "card");
        card.append(
          node("h3", label(id)),
          node("div", value(row), "value"),
          node("small", `n=${row.n ?? 0} · ${row.status}`, "status"),
        );
        const d = node("details");
        d.append(
          node("summary", "Definition"),
          node("p", report.definitions[id] || ""),
        );
        if (row.reason) d.append(node("p", row.reason));
        card.append(d);
        cards.append(card);
      }
      if (cards.childNodes.length) {
        s.append(cards);
        root.append(s);
      }
    }
    const trend = section("Activity over time"),
      metric = "commits";
    const points = filtered
      .filter((r) => r.metric === metric)
      .sort((a, b) => a.start.localeCompare(b.start));
    const chart = node("div", undefined, "chart"),
      valid = points.filter((r) => r.value !== null);
    if (valid.length) {
      const max = Math.max(1, ...valid.map((r) => r.value));
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 1000 130");
      svg.setAttribute("role", "img");
      svg.setAttribute(
        "aria-label",
        "Commit counts by period. Exact values follow in the table.",
      );
      let segment = [];
      function drawSegment() {
        if (!segment.length) return;
        const line = document.createElementNS(svg.namespaceURI, "polyline");
        line.setAttribute("points", segment.join(" "));
        line.setAttribute("fill", "none");
        line.setAttribute("stroke", "#176653");
        line.setAttribute("stroke-width", "3");
        svg.append(line);
        segment = [];
      }
      points.forEach((r, i) => {
        if (r.value === null) drawSegment();
        else
          segment.push(
            `${20 + (i * 960) / Math.max(1, points.length - 1)},${115 - (r.value / max) * 100}`,
          );
      });
      drawSegment();
      chart.append(svg);
    } else
      chart.append(node("p", "No covered commit observations in this range."));
    trend.append(
      chart,
      table(
        [
          "Period",
          "Commits",
          "Commit authors",
          "PRs opened",
          "Issues opened",
          "Discussions opened",
        ],
        points.map((p) => {
          const rows = filtered.filter(
            (r) => r.start === p.start && r.end === p.end,
          );
          return [
            p.start.slice(0, 10),
            ...[
              "commits",
              "commit_authors",
              "prs_opened",
              "issues_opened",
              "discussions_opened",
            ].map((id) => value(find(id, rows))),
          ];
        }),
        "Every row is calculated independently. Missing values indicate unavailable coverage.",
      ),
    );
    root.append(trend);
    if (project) {
      const s = section("Work awaiting a response"),
        sort = node("select");
      const staleDays = report.stale_days || 28;
      const ageLabel = node(
        "label",
        `Only items aged ${staleDays} days or more`,
      );
      const ageFilter = node("input");
      ageFilter.type = "checkbox";
      ageLabel.append(ageFilter);
      sort.setAttribute("aria-label", "Sort waiting work");
      [
        ["age", "Oldest first"],
        ["updated", "Latest activity"],
      ].forEach(([v, t]) => {
        const o = node("option", t);
        o.value = v;
        sort.append(o);
      });
      const list = node("ul", undefined, "waiting");
      function waiting() {
        list.replaceChildren();
        const rows = [...(report.waiting[scope] || [])]
          .filter((r) => !ageFilter.checked || r.age_days >= staleDays)
          .sort((a, b) =>
            sort.value === "age"
              ? b.age_days - a.age_days
              : b.updated_at.localeCompare(a.updated_at),
          );
        for (const row of rows) {
          const li = node("li");
          li.append(
            link(row.title, row.url),
            node(
              "small",
              `${row.kind} · ${row.age_days} days · ${row.reason}${row.age_days >= staleDays ? ` · ${staleDays}-day filter match` : ""}`,
            ),
          );
          list.append(li);
        }
        if (!rows.length)
          list.append(
            node(
              "li",
              "No waiting items in the collected snapshot. Check coverage before interpreting this result.",
            ),
          );
      }
      sort.addEventListener("change", waiting);
      ageFilter.addEventListener("change", waiting);
      waiting();
      s.append(
        node(
          "p",
          "Current snapshot only, up to 50 items. This list is separate from historical cohorts.",
          "scope-note",
        ),
        sort,
        ageLabel,
        list,
      );
      root.append(s);
      const releases = section("Release evidence");
      releases.append(
        table(
          ["Version / line", "Date evidence", "Archive"],
          (report.releases[scope] || [])
            .sort((a, b) =>
              b.version.localeCompare(a.version, undefined, { numeric: true }),
            )
            .map((r) => [
              link(r.version + " / " + r.line, r.url),
              r.at ? `${r.at} · ${r.date_kind}` : r.date_kind,
              link("Official archive", r.archive_url),
            ]),
        ),
      );
      root.append(releases);
      const shared = section("Shared development list");
      shared.append(
        link("View Logging-wide list activity", "./index.html#shared-list"),
        node(
          "p",
          "The shared list is not assigned to individual projects. Other mailing lists and historical JIRA records are outside coverage.",
        ),
      );
      if (project.jira)
        shared.append(link("Legacy issue tracker", project.jira));
      root.append(shared);
    } else {
      const s = section("Shared Logging development list");
      s.id = "shared-list";
      const rows = report.metrics.filter(
        (r) =>
          r.scope === "shared-list" && r.end === end && r.grouping === grouping,
      );
      s.append(
        link("Public dev-list archive", report.mail_archive),
        node(
          "p",
          "Public dev list only. Shared counts appear once and are not included in project totals.",
        ),
      );
      s.append(
        table(
          ["Metric", "Value", "Sample", "Coverage"],
          rows.map((r) => [
            label(r.metric),
            value(r),
            r.n,
            r.status + (r.reason ? " · " + r.reason : ""),
          ]),
        ),
      );
      root.append(s);
      const inactive = section("Inactive project catalogue");
      inactive.append(
        table(
          ["Project", "Official status", "Evidence"],
          report.inactive.map((p) => [
            link(p.name, p.url),
            p.status,
            link("Logging project catalogue", "https://logging.apache.org/"),
          ]),
        ),
      );
      root.append(inactive);
    }
  }
  render();
}
