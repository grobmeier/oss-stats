# Methodology

Definition version: 1.0. The generated report includes each metric's definition,
population size, source status, UTC window, and grouping.

## Periods and populations

Every reporting window includes its start and excludes its end. Monthly and
quarterly figures use original observations. Unique participants are unions
within each channel. Quarterly figures do not sum monthly headcounts or
average monthly medians.

Counts remain visible below five observations. Rates, medians, retention, and
concentration require five eligible observations. Suppressed values remain
distinct from zero. Partial-source figures describe only collected records.

Participation uses Git author identities, stable GitHub account IDs, and
normalised mail sender identities. These channels remain separate. Explicit
identity aliases and Git mailmap information can join known aliases. Display
names do not establish identity. Bot accounts are excluded from human metrics.
Unmatched aliases can count one person more than once.
Work-item counts include automated submissions. Responses must come from a
human. Automated submissions therefore contribute workload without inflating
human participation counts.

First observed GitHub or mail participation does not establish first-ever
participation. Git newcomer figures use full history of the selected branches.
Retention uses all known author cohorts eligible for 180 days of observation
before period end. It counts a second commit within 180 days of the first.

## Responses and historical states

A response is another human's comment, discussion reply, or formal PR review.
Self-responses, bots, reactions, assignments, and label changes do not count.
Issue and discussion cohorts use creation time. Review cohorts use the first
readiness event, or creation for an initially ready PR.

Latency medians include responses before period end. The same cohort's
unanswered count and share appear beside them. Recent cohorts have less time
to receive a response. Current waiting lists use the latest collected state
and remain separate from historical cohorts.

PR and issue lifecycle events reconstruct historical open states and draft
states. Missing readiness for an initially draft PR produces unavailable
latency. Conversions retain their source events when the API exposes them.
Full reconciliation removes records that no longer exist in the source.
Older local render snapshots preserve previously published observations.

GitHub does not expose a complete discussion answer-removal timeline through
the collected API. Answer metrics therefore use observed snapshots. They do
not apply current answers to earlier months. A category without answers is
outside the marked-answer denominator. An unmarked answer does not establish
that a question remains unresolved.

## Releases and source coverage

Official archive entries verify stable releases. Publication timestamps come
from GitHub release records when available. Undated archive entries remain
undated. Tag-only versions remain unverified. A tag is not proof of an
official distribution or its publication date.

Release counts with undated evidence carry a partial warning. A newer undated
version prevents a claim about the latest release's age. Release inactivity
does not establish abandonment or security status.

GitHub nested connections paginate until completion. Connection count
mismatches fail the source. Checkpoints retain earlier records and expose
failure or interrupted collection in coverage. Incremental reads overlap by
two days. A full reconciliation detects removals and refreshes every item.

The shared development list appears once at Logging scope. Threads use message
references. Messages without references are not joined by subject. Missing
references or roots outside the collected period can affect reply metrics.
Flume's other historical mailing channels and all legacy JIRA records remain
outside first-release coverage.

Flume's repository documents dormancy and rework. The dashboard preserves that
context. Inactive Logging projects appear in a separate catalogue and do not
contribute to current overview totals.

## Interpretation

Activity does not measure effort, quality, support promises, or security.
Review shares do not establish individual productivity. There is no health
score, individual ranking, or sentiment analysis.

## Backlog age distribution

Open PRs and issues enter one disjoint age bucket immediately before period end:
under 7 days, 7 to under 30 days, 30 to under 90 days, or 90 days or more.
Age starts at creation. Draft PRs and closed items are excluded. A reopened item
retains its original creation age. Bucket counts sum to the matching backlog.
PR buckets follow module filters. Issue buckets remain at repository scope.

## Newcomer journey

A cohort contains human authors whose first observed PR in the selected repository
or community was created during that period. Drafts count. Bots do not count.
The stored history does not establish first-ever participation. At community
scope, the same account counts once across repositories. Another PR in any
configured repository can count as a return. Module filters do not change cohorts.

Unlike backlog snapshots, cohort outcomes use the report timestamp as their
observation horizon. Historical cohorts can therefore gain outcomes in later
reports. The response outcome requires another human account's comment or review
on the first PR within 30 days of creation. Merge and return outcomes use 90 days.
A return means another PR in the same scope, with no merge requirement.

Each rate includes only authors whose full outcome window ends before the report
timestamp. Outcomes on the deadline count. Events at the report timestamp do not.
Counts describe those eligible authors, not incomplete windows. Each cohort shows
its eligible denominators. Rates below the configured sample floor remain
unavailable. Recent cohorts do not count as failures. Response, merge, and return
are separate outcomes. They do not form sequential funnel stages.

The same coverage rules apply to cohort and backlog metrics as to their PR or
issue source. Exports contain only aggregate counts, rates, and coverage states.
