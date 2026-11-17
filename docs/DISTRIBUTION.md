# OSS Stats: run your own community dashboard

The same application runs Logging, Maven, Commons, or your own repository catalogue.
Each archive includes configuration examples, licence, attribution, and a build manifest.
No collected data, credentials, or deployment access is included.

## Native executable

Extract the archive for your operating system and CPU. Open a terminal in the extracted directory.
The executable bundles Python, DuckDB, PyYAML, and the dashboard assets.
You do not need to install Python for this distribution.
Collection requires Git and the GitHub CLI (`gh`) on your PATH.
Authenticate with `gh auth login` using your own account before collection.
The application reads public repositories and the configured public Apache mailing list.

Run these commands from the extracted directory:

```sh
./oss-stats --help
./oss-stats --config config/maven.yaml collect
./oss-stats --config config/maven.yaml render
```

The Maven example covers Maven Core and Resolver. The Commons example
covers Lang and IO. Expand `projects` to select additional repositories.
Select `config/commons.yaml` or `config/logging.yaml` to use those examples.
You can also pass the path to your own YAML file.

Data stays in `data/<dashboard_id>`. Reports appear under `site/<dashboard_id>`.
The HTML, JavaScript, CSS, JSON, and CSV form a static website. Publish only the
resolved report directory. Never publish the private `data` directory.
Use any static web server to preview or publish the report.
The commands do not deploy anything or create a refresh schedule.
Run collection and rendering again to update the report.

Use `collect --sample 2 --months 3` for a smaller first check. Such a sample has
partial coverage and needs `render --allow-partial` for inspection.
Git history is still collected for the selected branches.
A full initial collection can take time and consume GitHub API quota.
Failures preserve checkpoints. Inspect coverage before publishing results.

## Python package

This archive includes a wheel and the same configuration examples.
Use Python 3.11 or later on macOS or Linux, with Git and authenticated `gh`.
From the extracted Python archive, install its wheel into an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/pip install ./oss_stats-*.whl
.venv/bin/oss-stats --config config/maven.yaml collect
.venv/bin/oss-stats --config config/maven.yaml render
python3 -m http.server 8129 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8129/maven/` after rendering.
Installation retrieves Python dependencies from the package index.
The application does not need its source checkout after installation.

## Platform and distribution limits

Native executables are specific to an operating system and CPU. A macOS ARM64
binary cannot run on Linux or an Intel Mac. Build on each target platform.
The build manifest records the build platform and dependency versions.
Linux binaries require a compatible glibc-based system. Alpine/musl is not supported.
Windows is not supported because collection uses POSIX locks and publication uses symlinks.
macOS binaries are not Developer ID signed or notarised. Distribution through
GitHub or a browser can therefore require the recipient's normal macOS approval.
This build does not change operating-system security settings.


## Build from source

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,packaging]'
.venv/bin/python -m pytest
.venv/bin/python scripts/build_distribution.py --binary
```

Outputs are in `dist/distribution/`. Each archive has a SHA-256 checksum file.
`BUILD.json` records the source revision, dirty state, dependency versions, and file hashes.
A dirty build is suitable for local checks. Share release builds from a clean commit.
The builder copies only the explicit distribution files and bundled dependencies.
It does not copy the source checkout, environment, caches, or private datasets.

Adapted from Russell Spitzer's Iceberg Community Health under Apache-2.0.
The exact upstream revision and additional credits are in `PROVENANCE.md` and `NOTICE`.
