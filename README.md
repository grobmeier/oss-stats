# OSS Stats

A configurable community activity dashboard for open-source projects.
The Apache Logging configuration covers
Log4j, Log4j Kotlin, Log4cxx, Log4net, Flume, and the shared Logging development
list. It includes pull requests, GitHub Issues, Discussions, Git history, and
official release evidence. It does not calculate sentiment or a health score.

This project adapts **Russell Spitzer's
[Iceberg Community Health](https://github.com/RussellSpitzer/iceberg-community-health)**.
See [provenance](docs/PROVENANCE.md) for the exact reference revision and
attribution. Apache-2.0. This project does not claim ASF endorsement.

The report index is **https://stats.grobmeier.de/**. The Logging report is at
**https://stats.grobmeier.de/logging/**.
Refresh is manual. No scheduled collection or publication is enabled.
See [deployment and refresh](docs/DEPLOYMENT.md).

## Local setup

Use Python 3.11 or later, Git, and an authenticated GitHub CLI (`gh`).
The collector only reads public project data. Use a dedicated credential with
the least permissions available for public reads.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

## Collect and preview

Run commands from this repository root. Data and rendered reports remain
local and ignored by Git.

Start with a small live sample. Git history is complete even in sample mode.
GitHub item counts are bounded per channel. Mail uses the latest completed
month and the current month. The report labels sampled channels as partial.

```sh
.venv/bin/oss-stats --data data/local collect --sample 2
.venv/bin/oss-stats --data data/local render --allow-partial
.venv/bin/python -m http.server 8129 --bind 127.0.0.1 --directory site
```

Open [the local dashboard](http://127.0.0.1:8129/logging/).
The first Git collection can take several minutes.

Collect the full configured history, then render a complete report:

```sh
.venv/bin/oss-stats --data data/local collect --full
.venv/bin/oss-stats --data data/local render
```

Use the same data directory to resume interrupted collection:

```sh
.venv/bin/oss-stats --data data/local collect
```

Source checkpoints preserve completed nested reads. A later ordinary collection
can reuse unchanged items. `--full` deliberately reads every item again and
reconciles confirmed removals. Use it periodically or after source changes.

`--months 12` selects a shorter initial window. `--projects log4j kotlin`
limits repository collection. `--request-budget 3000` bounds GitHub requests.
Omitted Git or mail sources display unavailable, rather than zero.
Collection exits with status 1 when any source fails or remains unavailable.
Review coverage before using `render --allow-partial`.

The default history is 72 completed months, with the partial current month
separate. Branch metadata comes from GitHub. The collector does not assume
`main`. Configure additional branches explicitly in `config/logging.yaml`.

## Output and data boundaries

- `data/`: private local Parquet snapshots, collection state, and Git caches.
- `site/logging/`: current static snapshot, reached through an atomic symlink.
- `site/.logging-snapshots/`: complete older render versions.
- `metrics.json` and `metrics.csv`: versioned public aggregate exports.

Publish only the resolved static snapshot. Never publish `data/` or the
repository root. HTML assets use relative links and work below `/logging/`.
The browser needs no token, live GitHub connection, or database.

Mail and comment bodies are not retained. Internal identity keys do not enter
public exports. Waiting-work titles are escaped and email addresses are
omitted. Cross-channel identities remain separate.

See the [methodology](docs/METHODOLOGY.md) and [operations guide](docs/OPERATIONS.md).

## Reuse for another community

The same application supports separate communities through YAML configuration.
See [configuration and reuse](docs/CONFIGURATION.md). Starter configurations exist
for Maven Core and Resolver, and Commons Lang and IO. These are initial
catalogues, not complete inventories of Maven or Commons repositories.

```sh
.venv/bin/oss-stats --config config/maven.yaml collect
.venv/bin/oss-stats --config config/maven.yaml render
.venv/bin/oss-stats --config config/commons.yaml collect
.venv/bin/oss-stats --config config/commons.yaml render
```

Each configuration selects its own data directory, output directory, page
navigation, shared list, and URL path. Adding repositories requires configuration
changes and collection. It requires no application code changes.

Range controls update charts automatically. Custom months receive validation.
Project links retain the selected months and grouping. Cards show the latest
selected period. Sparklines and absolute changes compare periods within the
selected interval. Counts of people and response medians are never summed.
The reload button checks the latest published snapshot without starting collection.

Backlog age charts partition open PRs and issues into four disjoint age buckets.
The newcomer journey shows first-observed PR cohorts, human responses within
30 days, and merges and return PRs within 90 days. Rates use only fully observed
windows and retain sample-size limits. See [methodology](docs/METHODOLOGY.md).

## Shareable distributions

Build a native macOS or Linux executable and a Python-wheel archive with example
configurations. Recipients can run Maven or another catalogue without cloning
this repository. See [distribution instructions](docs/DISTRIBUTION.md).
Native packages include Python and its libraries. Collection still needs Git
and authenticated GitHub CLI. The manual distribution workflow builds and tests
platform-specific archives without publishing a release or deploying a website.

The installable package, command, and native executable are named `oss-stats`.
The installed Python package also provides `logging-stats` as a compatibility
alias for existing operator scripts. The source module remains `logging_stats`.
The source repository is [grobmeier/oss-stats](https://github.com/grobmeier/oss-stats).
