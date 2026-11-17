# Operation

## Repeat a collection

Run collection and rendering with the same configuration and data directory:

```sh
oss-stats --config config/commons.yaml collect
oss-stats --config config/commons.yaml render
```

Ordinary collection reuses checkpoints and refreshes changed sources.
Use `collect --full` to reconcile edits, transfers, and source removals.

## Recover from failure

1. Inspect the report's source status and the collection command's error.
2. Check GitHub authentication and API allowance with `gh api rate_limit`.
3. Repeat ordinary collection against the same data directory.
4. Check every failed, unavailable, or partial source.
5. Render and publish after required collection succeeds.

`render --allow-partial` permits a local preview with visible source warnings.
The normal render command refuses incomplete sources.

Use `--months` for a shorter initial history window and `--request-budget` to
bound GitHub requests. `--projects` selects repository IDs from the configuration.
Omitting Git or mail collection marks those sources unavailable.

## Storage and scope

Private snapshots and Git caches stay under the configured data directory.
Reports and earlier render versions stay under the output directory's parent.
No automatic pruning runs. Inspect retained versions before deleting them.

Changing selected branches or the repository catalogue can change comparisons.
Use a separate store when comparing different collection scopes.

Publish the resolved report snapshot rather than the repository or data directory.
Retain a complete published version for recovery if a later update fails.
