# OSS Stats

OSS Stats builds static activity dashboards for open-source communities.
Configure repositories and a shared development list, collect public data,
and publish the generated files on any static web host.

Reports cover contributions, pull requests, GitHub Issues and Discussions,
releases, and mailing-list activity. Charts support monthly and quarterly views.
Metric definitions and source status accompany the results.

## Examples

The repository includes three example configurations:

| Example | Included projects | Configuration |
| --- | --- | --- |
| Apache Commons | Lang and IO | [commons.yaml](config/commons.yaml) |
| Apache Maven | Core and Resolver | [maven.yaml](config/maven.yaml) |
| Apache Logging | Log4j, Log4j Kotlin, Log4cxx, Log4net, and Flume | [logging.yaml](config/logging.yaml) |

These catalogues can be extended through configuration.
An example deployment is available at [stats.grobmeier.de](https://stats.grobmeier.de/).
Use your own hostname and hosting setup when publishing a dashboard.

## Install

Use Python 3.11 or later on Linux or macOS. Collection also needs Git and
an authenticated GitHub CLI (`gh`).

```sh
python3 -m venv .venv
.venv/bin/pip install .
gh auth login
```

Prebuilt executable and Python-wheel archives are also supported.
See [distribution instructions](docs/DISTRIBUTION.md).

## Collect and render

Choose a configuration and run these commands from the repository root:

```sh
.venv/bin/oss-stats --config config/maven.yaml collect
.venv/bin/oss-stats --config config/maven.yaml render
.venv/bin/python -m http.server 8129 --bind 127.0.0.1 --directory site
```

Open [the local Maven example](http://127.0.0.1:8129/maven/).
Use another example file or your own YAML file to select a different community.

The first collection reads the configured history and can take time.
Later runs reuse checkpoints. A smaller preview is available with
`collect --sample 2 --months 3` and `render --allow-partial`.
Sampled results are marked as partial.

Collection is read-only. It does not change repositories, issues, or discussions.
The CLI does not schedule jobs or deploy reports.

## Configure your community

Copy an example file and edit its title, repository catalogue, URL path,
and optional shared mailing list. Each community has separate data and output
paths. See [configuration](docs/CONFIGURATION.md) for supported fields.

Publish only the resolved report directory under `site/`. Data, credentials,
and collection state must stay outside the public web root.
See [static hosting](docs/DEPLOYMENT.md) and [operation](docs/OPERATIONS.md).

Reports use public observations rather than sentiment analysis or a health score.
See [methodology](docs/METHODOLOGY.md) for definitions and limitations.

## Development

```sh
.venv/bin/pip install -e '.[dev,packaging]'
.venv/bin/python -m pytest
node --test tests/view.test.cjs
node --check src/oss_stats/web/app.js
```

The Python package is `oss_stats`; the command is `oss-stats`.
Build instructions and standalone checks are in [distribution](docs/DISTRIBUTION.md).

## Licence and attribution

Licensed under [Apache-2.0](LICENSE).
OSS Stats includes calendar helpers from Russell Spitzer's
[iceberg-community-health](https://github.com/RussellSpitzer/iceberg-community-health)
and adapts its reporting approach. See [provenance](docs/PROVENANCE.md) and [NOTICE](NOTICE).
