# Static hosting

A rendered report is a static website. It needs no application server, database,
or GitHub credential on the public host.

## Publish a report

1. Collect the configured sources.
2. Render the complete report.
3. Resolve the output symlink.
4. Copy only that snapshot's files to your static host.
5. Serve them under the configured `base_path`.
6. Check the overview, project links, scripts, styles, and aggregate downloads.

For the Maven example, the render command is:

```sh
oss-stats --config config/maven.yaml render
```

Its output is `site/maven/`. Other examples use their own community directories.
Assets use relative links, so each report can be served below its own path.

Keep `data/`, Git caches, credentials, and the source checkout outside the web
root. Preserve the previous complete report until a replacement passes validation.
Do not publish a partial preview as a complete report.

## Refresh

Opening the website does not collect new data. To refresh a report, run collection
and rendering again, then publish the resulting snapshot.

A scheduler can run those commands periodically on a worker of your choice.
Stop publication when collection or rendering fails. The CLI returns a failure
status and retains checkpoints for another attempt.

Configure the static host to revalidate cached files, so visitors receive newly
published data. Publish files together, with an atomic directory switch when
supported by the host.

The reports at [stats.grobmeier.de](https://stats.grobmeier.de/) are one example
of this setup. Their hosting and schedule are not requirements of OSS Stats.
