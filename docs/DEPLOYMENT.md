# Deployment and refresh

The dashboard is live at [stats.grobmeier.de/logging](https://stats.grobmeier.de/logging/).

## Published service

## Refresh behaviour

Refresh is currently manual. Opening or reloading the website does not start collection.
The browser retrieves the last published snapshot. The page shows report time and source freshness.

From this checkout, run these commands in order:

Collection and publication run on demand. No recurring job is configured.
Periodic `collect --full` runs can reconcile source edits, transfers, and removals.

## Maintainer checks

The helper checks Caddy, the active release, public files, redirects, and private-path rejection.
The full infrastructure procedure is in the maintainer repository's `docs/logging-stats.md`.
