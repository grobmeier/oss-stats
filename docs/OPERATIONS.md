# Operation

## Collection recovery

1. Inspect the Coverage section or `data/local/state.json`.
2. Check GitHub authentication without printing credential values.
3. Check the remaining API allowance with `gh api rate_limit`.
4. Run ordinary collection against the same data directory.
5. Review all failed, unavailable, and partial sources.
6. Render the complete snapshot after the required sources succeed.

Use `--full` for a reconciliation after repository transfers, identity-rule
changes, or source deletions. The operation retains earlier Parquet versions.
Old snapshots can require disk cleanup after review. No pruning runs
automatically.

Changes to selected branches change the meaning of commit comparisons. Review
the recorded branch scope before publishing comparisons after such a change.
Use a new data directory for a deliberately different scope when historical
comparability is required.

## Static publication

Render the static snapshot into `site/logging/`. Resolve its symlink before
copying files. The snapshot contains HTML, CSS, JavaScript, aggregate JSON,
and CSV. It does not require a server runtime.

The static host must serve `/logging/` and the relative assets below it.
It must not expose the repository, internal data, Git caches, or other render
versions. Validate the exact deployed files and all five project links.
Retain the previous complete snapshot for rollback.

Do not replace a complete public report with incomplete data without an
explicit publishing decision. A local partial preview needs the deliberate
`--allow-partial` option and displays source warnings.
