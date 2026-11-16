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
      : n.toFixed(/concentration/.test(row.metric) ? 3 : 1);
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
  n.id = title.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  n.append(node("h2", title));
  return n;
}
fetch("./metrics.json", {cache: "no-store"})
  .then((r) => {
    if (!r.ok) throw Error("Report could not be loaded");
    return r.json();
  })
  .then(start)
  .catch((e) => {
    $("freshness").textContent = e.message;
  });
$("reload").addEventListener("click", () => {
  const button = $("reload");
  button.disabled = true;
  fetch("./metrics.json", {cache: "no-store"})
    .then(r => { if (!r.ok) throw Error("The published report could not be reloaded."); return r.json(); })
    .then(report => { start(report); $("freshness").append(" · Published snapshot checked just now."); })
    .catch(error => { $("freshness").textContent = error.message + " The current view remains available."; })
    .finally(() => { button.disabled = false; });
});
function start(report) {
  if (report.schema_version !== 1 || !Array.isArray(report.metrics) || !Array.isArray(report.projects))
    throw Error("Unsupported published report format.");
  ["warning", "definitions", "sources"].forEach(id => $(id).replaceChildren());
  $("module").replaceChildren(new Option("All modules", ""));
  $("module-label").hidden = true;
  const overview = report.dashboard_id || "logging";
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
      (scope === overview ||
        key.startsWith(scope + ":") ||
        key === overview + ":mail") &&
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
      scope === overview ||
      key.startsWith(scope + ":") ||
      key === overview + ":mail",
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
  if (!latest) throw Error("No report periods are available.");
  for (const id of ["from", "to"]) {
    $(id).min = dates[0]; $(id).max = latest;
  }
  function setRange() {
    const n = Number($("range").value);
    if (n) { $("from").value = dates[Math.max(0, dates.length - n)]; $("to").value = latest; }
  }
  function restore() {
    const params = new URLSearchParams(location.search);
    $("range").value = "12"; $("group").value = "monthly"; $("module").value = "";
    setRange();
    if (params.has("from")) $("from").value = params.get("from");
    if (params.has("to")) $("to").value = params.get("to");
    if (["monthly", "quarterly", "partial month"].includes(params.get("group"))) $("group").value = params.get("group");
    if (project?.modules && Object.hasOwn(project.modules, params.get("module"))) $("module").value = params.get("module");
    if (params.has("from") || params.has("to")) $("range").value = "custom";
  }
  restore();
  $("range").onchange = () => { setRange(); render(); };
  for (const id of ["from", "to"]) $(id).onchange = () => { $("range").value = "custom"; render(); };
  for (const id of ["group", "module"]) $(id).onchange = render;
  $("reset").onclick = () => {
    $("range").value = "12"; $("group").value = "monthly"; $("module").value = "";
    setRange(); render();
  };
  $("filters").onsubmit = e => { e.preventDefault(); render(); };
  window.onpopstate = () => { restore(); render(); };
  function render() {
    const root = $("dashboard");
    const partial = $("group").value === "partial month";
    for (const id of ["from", "to", "range"]) $(id).disabled = partial;
    const error = partial ? "" : CommunityView.range($("from").value, $("to").value, dates);
    $("range-status").textContent = error || (partial ? "Current partial month. Compare it only with other partial periods." : `Trend interval: ${$("from").value} through ${$("to").value}.`);
    for (const id of ["from", "to"]) $(id).setAttribute("aria-invalid", String(Boolean(error)));
    if (error) { $("range-status").className = "notice"; return; }
    $("range-status").className = "scope-note";
    const query = CommunityView.query({from: $("from").value, to: $("to").value, group: $("group").value, module: $("module").value});
    history.replaceState(null, "", location.pathname + "?" + query + location.hash);
    document.querySelectorAll('nav[aria-label="Projects"] a').forEach(a => {
      const url = new URL(a.href); url.search = query; a.href = url.href;
    });
    root.replaceChildren();
    const selected = scope + ($("module").value ? "/" + $("module").value : "");
    const repositoryMetric = (name) =>
      /^(?:new_)?(?:issue|discussion)|^(?:stable_releases|release_age_days)$/.test(
        name,
      );
    const grouping = $("group").value;
    const filtered = report.metrics.filter(
      (r) =>
        (r.scope === selected ||
          ($("module").value &&
            r.scope === scope &&
            repositoryMetric(r.metric))) &&
        r.grouping === grouping &&
        (grouping === "partial month" ||
          (r.start.slice(0, 7) >= $("from").value &&
            r.end <= CommunityView.endExclusive($("to").value))),
    );
    if (!filtered.length) {
      root.append(node("p", "No complete periods match this range. Quarters must fit entirely inside the selected months."));
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
    if (scope === overview) {
      const s = section("Across the projects");
      s.append(
        table(
          [
            "Project",
            "Commit authors",
            "Open PRs",
            "Open issues",
            "Latest release evidence",
            "Coverage",
          ],
          report.projects.map((p) => {
            const rows = report.metrics.filter(
              (r) =>
                r.scope === p.id && r.end === end && r.grouping === grouping,
            );
            const name = node("span");
            name.append(link(p.name, "./" + p.id + ".html?" + query));
            if (p.status)
              name.append(node("small", " · " + (p.status_short || "See project status")));
            const latestRelease = [...(report.releases[p.id] || [])]
              .filter((r) => r.verified)
              .sort((a, b) =>
                b.version.localeCompare(a.version, undefined, {
                  numeric: true,
                }),
              )[0];
            const releaseCell = latestRelease ? node("span") : "Unavailable";
            if (latestRelease)
              releaseCell.append(
                link(latestRelease.version, latestRelease.url),
                node(
                  "small",
                  latestRelease.at
                    ? " · " + latestRelease.at.slice(0, 10)
                    : " · Date unavailable",
                ),
              );
            return [
              name,
              value(find("commit_authors", rows)),
              value(find("pr_backlog", rows)),
              value(find("issue_backlog", rows)),
              releaseCell,
              Object.entries(report.sources)
                .filter(([key]) => key.startsWith(p.id + ":"))
                .map(([, v]) => v.status)
                .filter((v, i, a) => a.indexOf(v) === i)
                .join(", "),
            ];
          }),
          "Project headcounts overlap. Release evidence uses the latest collected snapshot, independently of the selected activity period.",
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
      if (
        $("module").value &&
        ["Issues", "Discussions", "Releases"].includes(title)
      ) {
        s.append(
          node(
            "p",
            "Repository scope. The module filter applies to commits and pull requests.",
            "scope-note",
          ),
        );
      }
      for (const id of ids) {
        const row = find(id);
        if (!row) continue;
        const card = node("div", undefined, "card");
        card.append(
          node("h3", label(id)),
          node("div", value(row), "value"),
          node("small", `n=${row.n ?? 0} · ${row.status}`, "status"),
        );
        const series = filtered.filter(r => r.metric === id).sort((a, b) => a.start.localeCompare(b.start));
        card.append(plot([{name: label(id), points: series}], true));
        const change = CommunityView.delta(series);
        const formatted = change === null ? "Change unavailable" : `${change > 0 ? "+" : ""}${/share|retention/.test(id) ? (change * 100).toFixed(1) + " percentage points" : value({...row, value: change})} from first period`;
        card.append(node("small", formatted, "delta"));
        const d = node("details");
        d.append(
          node("summary", "Definition"),
          node("p", report.definitions[id] || ""),
        );
        if (row.reason) d.append(node("p", row.reason));
        card.append(d);
        const history = node("details"); history.append(node("summary", "Period values"));
        history.append(table(["Period", "Value", "Coverage"], series.map(r => [r.start.slice(0, 10), value(r), r.status])));
        card.append(history);
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
    const chart = node("div", undefined, "trend-grid");
    const chartGroups = [
      ["Contributions", ["commits", "commit_authors"]],
      ["Pull request flow", ["prs_opened", "prs_merged", "prs_closed"]],
      ["Open work at period end", ["pr_backlog", "issue_backlog"]],
      ["First human response · hours", ["first_review_hours", "issue_reply_hours", "discussion_reply_hours"]],
      ["Unanswered cohort share · percent", ["pr_unreviewed_share", "issue_unanswered_share", "discussion_unanswered_share"]],
    ];
    for (const [title, metrics] of chartGroups) {
      const panel = node("div", undefined, "trend-panel");
      panel.append(node("h3", title));
      const series = metrics.map(metric => ({name: label(metric), points: filtered.filter(r => r.metric === metric).sort((a, b) => a.start.localeCompare(b.start))}));
      panel.append(plot(series));
      const details = node("details"); details.append(node("summary", "Exact chart values"));
      details.append(table(["Period", ...series.map(s => s.name)], points.map(p => [p.start.slice(0, 10), ...series.map(s => value(s.points.find(r => r.start === p.start)))])));
      panel.append(details); chart.append(panel);
    }
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
          "Current repository snapshot only, up to 50 items. This list is separate from historical cohorts.",
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
              link("Release evidence", r.archive_url),
            ]),
        ),
      );
      root.append(releases);
      const shared = section("Shared development list");
      shared.append(
        link("View shared list activity", "./index.html?" + query + "#shared-list"),
        node(
          "p",
          "The shared list is not assigned to individual projects. Other mailing lists and historical JIRA records are outside coverage.",
        ),
      );
      if (project.jira)
        shared.append(link("Legacy issue tracker", project.jira));
      if (report.mail_archive || project.jira) root.append(shared);
    } else {
      const s = section("Shared development list");
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
      if (report.mail_archive) root.append(s);
      const inactive = section("Inactive project catalogue");
      inactive.append(
        table(
          ["Project", "Official status", "Evidence"],
          report.inactive.map((p) => [
            link(p.name, p.url),
            p.status,
            link("Project status", p.url),
          ]),
        ),
      );
      if (report.inactive.length) root.append(inactive);
    }
    $("sections").replaceChildren();
    [...root.querySelectorAll("section"), $("methodology"), $("coverage")].forEach(s => {
      $("sections").append(link(s.querySelector("h2").textContent, "#" + s.id));
    });
  }
  render();
}

function plot(series, compact = false) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", compact ? "0 0 320 64" : "0 0 640 240");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", series.map(s => s.name).join(", ") + ". Missing values form gaps. Exact values follow in the table.");
  svg.classList.add(compact ? "sparkline" : "trend-chart");
  const rows = series.flatMap(s => s.points).filter(r => r.value !== null);
  const maximum = Math.max(1, ...rows.map(r => r.value));
  const percent = rows.length && rows.every(r => /share|retention/.test(r.metric));
  const left = compact ? 3 : 64, right = compact ? 317 : 620, top = 8, bottom = compact ? 56 : 198;
  const colors = ["#176653", "#ad531c", "#415bb0"];
  function element(tag, attrs, text) {
    const e = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
    if (text !== undefined) e.textContent = text;
    svg.append(e); return e;
  }
  if (!compact) {
    for (const factor of [0, .5, 1]) {
      const y = bottom - factor * (bottom - top);
      element("line", {x1: left, x2: right, y1: y, y2: y, stroke: "#d9e3dd"});
      element("text", {x: left - 8, y: y + 4, "text-anchor": "end", "font-size": 12}, (maximum * factor * (percent ? 100 : 1)).toLocaleString(undefined, {maximumFractionDigits: 1}));
    }
    const points = series[0]?.points || [];
    [0, points.length - 1].forEach((i, j) => {
      if (points[i]) element("text", {x: j ? right : left, y: 225, "text-anchor": j ? "end" : "start", "font-size": 12}, points[i].start.slice(0, 7));
    });
  }
  series.forEach((s, index) => {
    let segment = [];
    function draw() {
      if (segment.length) element("polyline", {points: segment.join(" "), fill: "none", stroke: colors[index % colors.length], "stroke-width": compact ? 2 : 2.5});
      segment = [];
    }
    s.points.forEach((r, i) => {
      if (r.value === null) { draw(); return; }
      const x = left + i * (right - left) / Math.max(1, s.points.length - 1);
      const y = bottom - r.value / maximum * (bottom - top);
      segment.push(`${x},${y}`);
      if (!compact || s.points.length === 1) {
        const dot = element("circle", {cx: x, cy: y, r: 3, fill: colors[index % colors.length], tabindex: 0});
        const title = document.createElementNS(ns, "title"); title.textContent = `${s.name}, ${r.start.slice(0, 7)}: ${value(r)} (${r.status})`; dot.append(title);
      }
    }); draw();
  });
  const wrap = node("div", undefined, compact ? "spark-wrap" : "chart");
  if (!rows.length) wrap.append(node("p", "No covered values for this interval."));
  else wrap.append(svg);
  if (!compact) {
    const legend = node("div", undefined, "legend");
    series.forEach((s, i) => { const key = node("span", s.name); key.className = "series-" + i; legend.append(key); });
    wrap.append(legend);
  }
  return wrap;
}
