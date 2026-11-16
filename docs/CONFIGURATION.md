# Community configuration

Run commands from the repository root. Select a YAML file with `--config`.
Logging remains the default. Maven and Commons use separate configurations.

## Fields

| Field | Purpose |
| --- | --- |
| `dashboard_id` | Stable community ID and overview metric scope. Use lowercase letters, digits, and hyphens. |
| `title`, `brand` | Page heading and header text. |
| `base_path` | One public directory, such as `/maven/`. |
| `target_url` | Intended public URL. |
| `projects` | Explicit repository catalogue with unique `id`, display `name`, and GitHub `repo`. |
| `data_dir` | Private directory. Defaults to `data/<dashboard_id>`. |
| `output_dir` | Static output symlink. Defaults to `site/<dashboard_id>`. |
| `mail` | Optional shared Apache PonyMail list: `list`, `domain`, `archive`. Omit it for GitHub-only dashboards. |
| `history_months` | Number of complete monthly periods. Default: 72. |
| `sample_floor`, `stale_days` | Minimum samples for rates and medians, and waiting-work age threshold. Defaults: 5 and 28. |
| `bot_patterns`, `identity_aliases` | Internal identity rules. These do not enter public exports. |
| `inactive` | Optional catalogue of inactive projects, with `name`, `url`, and `status`. |

Each project can configure `modules` as named path-prefix lists. These filters
apply to commits and pull requests. They can overlap. `status`, `status_short`,
`status_url`, and `jira` provide optional context and evidence links.

## Releases

`release_pattern` must contain a named `version` group. The default matches
`1.2.3` and `v1.2.3`. Set repository-specific tag rules when necessary.
With `archive`, versions must also appear in the configured official archive.
Without `archive`, the collector uses non-draft, non-prerelease GitHub releases
that match the pattern. It labels these as repository evidence. Tags alone do
not become published releases. An empty GitHub release list means no evidence
from that source, not that the project never released anything.

The Maven and Commons configurations use GitHub release evidence.
Review archive layout and version rules before adding official archive evidence.

## Data separation and catalogue changes

The CLI binds each private directory to its community, repository IDs, and mail
source. It rejects reuse by another community or a changed repository under an
existing ID. Select a new `--data` directory for those changes. Adding or removing
repository entries is supported. Removed entries remain private and do not enter
the current report. Reintroducing the same ID requires the original repository.
Logging retains its existing `data/local` directory through explicit configuration.

A new repository needs collection before complete publication. Coverage remains
unavailable until that collection succeeds. `render --allow-partial` supports
local inspection. The production publisher rejects incomplete coverage.

## Publication

Collection and publication remain manual. The public reload button only checks
for a newer published report. It preserves the selected range and grouping.
