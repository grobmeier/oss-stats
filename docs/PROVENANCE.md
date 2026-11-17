# Provenance

OSS Stats uses Russell Spitzer's
[iceberg-community-health](https://github.com/RussellSpitzer/iceberg-community-health)
as its source reference for historical collection, Parquet storage, and static reporting.

Reference revision: [`5e26873783da1849343a7c3dd0403f9ef56240d4`](https://github.com/RussellSpitzer/iceberg-community-health/tree/5e26873783da1849343a7c3dd0403f9ef56240d4).
The upstream project is licensed under Apache-2.0.

## Source attribution

The functions in `src/oss_stats/timeutil.py` match the upstream
`src/iceberg_community_health/timeutil.py` at the referenced revision.
The file retains Russell Spitzer's attribution.

The collection, checkpoint storage, and dashboard design adapt the upstream
approach. OSS Stats implements configurable communities and separate GitHub
Issues and Discussions models. Its metric definitions are documented in
[METHODOLOGY.md](METHODOLOGY.md).

The upstream NOTICE credits metric definitions to Patrick McFadin's
[cassandra-project-health](https://github.com/pmcfadin/cassandra-project-health),
under Apache-2.0. That indirect attribution is retained in [NOTICE](../NOTICE).

The upstream Apache Magpie submodule is not a dependency of OSS Stats.
Upstream datasets and generated reports are not distributed with this project.

## Licence files

[LICENSE](../LICENSE) contains Apache-2.0. [NOTICE](../NOTICE) records project
and upstream attribution. Source files carry Apache-2.0 headers.
Native distributions also include the bundled dependencies' licence files.
