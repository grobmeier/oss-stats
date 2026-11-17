# Configuration

Select a YAML file with `oss-stats --config path/to/community.yaml`.
Commons, Maven, and Logging examples are included in `config/`.
If `--config` is omitted, the CLI uses `config/logging.yaml`.

## Example

```yaml
dashboard_id: example
title: Example Community
brand: Example Stats
base_path: /example/
history_months: 12
projects:
  - id: example-project
    name: Example Project
    repo: owner/repository
```

Replace the repository placeholder with a public GitHub repository.
The report path is relative to your web host; no particular hostname is required.

## Fields

| Field | Purpose |
| --- | --- |
| `dashboard_id` | Community identifier and overview scope. Use lowercase letters, digits, and hyphens. |
| `title`, `brand` | Page heading and header text. |
| `base_path` | Public path, such as `/example/`. |
| `projects` | Repository entries with `id`, `name`, and `repo` in `owner/name` format. |
| `data_dir` | Local collection directory. Default: `data/<dashboard_id>`. |
| `output_dir` | Generated report symlink. Default: `site/<dashboard_id>`. |
| `history_months` | Complete monthly periods to collect. Default: 72. |
| `sample_floor` | Minimum sample for rates and medians. Default: 5. |
| `stale_days` | Waiting-work age threshold. Default: 28. |
| `mail` | Optional shared Apache mailing list with `list`, `domain`, and `archive`. |
| `inactive` | Optional informational catalogue with `name`, `url`, and `status`. |

Omit `mail` for a dashboard without mailing-list collection.
For an Apache development list, set `list: dev`, the community's mail domain,
and the archive URL. Shared mail metrics appear once in the overview.

Project entries can define additional `branches` and named `modules` containing
path prefixes. Module filters apply to commits and pull requests. The default
branch comes from GitHub. `status`, `status_short`, `status_url`, and `jira`
can supply project context and links.

## Release sources

`release_pattern` must contain a named `version` group. The default matches
`1.2.3` and `v1.2.3`. Configure the pattern for the repository's tag names.

Without `archive`, the collector reads matching published GitHub releases.
With `archive`, versions must also appear in the configured official archive.
Tag-only versions do not establish a published release. An empty GitHub release
list does not establish that a project has never released software.

The Maven and Commons examples currently use GitHub release records. The Logging
example also configures official archives for selected projects.

## Catalogue changes

Keep each community's data in its own directory. The collector rejects a changed
community identifier, mail source, or repository identity in an existing store.
Use `--data` to select a separate store when those identities change.

You can add repository entries to an existing community. Collect their history
before publishing the expanded report. Removed entries no longer contribute to
that report. Inspect partial results locally with `render --allow-partial`.

Each output directory is an atomic symlink to a complete render. Your publishing
process must copy its resolved contents and serve the configured `base_path`.
