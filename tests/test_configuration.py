# Copyright 2026 Christian Grobmeier and contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
import copy
import json

import pytest
import yaml

from oss_stats.config import load
from oss_stats.metrics import build_report
from oss_stats.render import publish
from oss_stats.store import Store


def test_three_catalogues_are_independent_and_generate_their_own_pages(tmp_path):
    for name in ('logging', 'maven', 'commons'):
        config = load(f'config/{name}.yaml')
        config['history_months'] = 1
        store = Store(tmp_path / name)
        store.bind(config)
        for p in config['projects']:
            store.save(p['id'] + ':commits', [{'id': 'sha', 'actor': 'author', 'at': '2026-10-04T00:00:00Z'}], {'status': 'complete'})
        report = build_report(store, config, '2026-11-16T00:00:00Z')
        row = next(r for r in report['metrics'] if r['scope'] == name and r['metric'] == 'commits' and r['grouping'] == 'monthly')
        assert row['value'] == len(config['projects'])
        output = tmp_path / 'site' / name
        publish(report, output)
        assert len(list(output.glob('*.html'))) == 1 + len(config['projects'])
        html = (output / 'index.html').read_text()
        assert config['brand'] in html
        assert 'Russell Spitzer' in html
        if name != 'logging':
            assert './log4j.html' not in html
        changed = copy.deepcopy(config)
        changed['projects'][0]['repo'] = 'another/repository'
        with pytest.raises(ValueError, match='different catalogue'):
            store.bind(changed)


def test_optional_mail_and_disabled_sources_do_not_make_aggregate_partial(tmp_path):
    config = load('config/maven.yaml')
    config['mail'] = None
    config['history_months'] = 1
    store = Store(tmp_path / 'data')
    store.save('maven-core:discussions', [], {'status': 'complete'})
    store.save('resolver:discussions', [], {'status': 'disabled'})
    report = build_report(store, config, '2026-11-16T00:00:00Z')
    assert 'maven:mail' not in report['sources']
    assert not any(r['scope'] == 'shared-list' for r in report['metrics'])
    row = next(r for r in report['metrics'] if r['scope'] == 'maven' and r['metric'] == 'discussions_opened' and r['grouping'] == 'monthly')
    assert row['status'] == 'complete' and row['value'] == 0


@pytest.mark.parametrize('pid', ['../escape', 'index', 'maven', 'shared-list'])
def test_config_rejects_unsafe_or_reserved_pages(tmp_path, pid):
    config = load('config/maven.yaml')
    config['projects'][0]['id'] = pid
    path = tmp_path / 'invalid.yaml'
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        load(path)


def test_catalogue_can_grow_and_removed_sources_remain_private(tmp_path):
    config = load('config/maven.yaml')
    store = Store(tmp_path)
    store.bind(config)
    extra = {'id': 'plugin', 'name': 'Plugin', 'repo': 'apache/maven-compiler-plugin'}
    config['projects'].append(extra)
    store.bind(config)
    store.save('plugin:commits', [], {'status': 'complete'})
    config['projects'].pop()
    store.bind(config)
    config['history_months'] = 1
    report = build_report(store, config, '2026-11-16T00:00:00Z')
    assert 'plugin:commits' not in report['sources']


def test_github_release_policy_excludes_tags_drafts_and_prereleases():
    from oss_stats.collect import release_records
    class API:
        def pages(self, endpoint):
            assert endpoint.endswith('/releases')
            base = {'tag_name': 'v1.2.3', 'draft': False, 'prerelease': False, 'published_at': '2026-10-01T00:00:00Z', 'html_url': 'https://github.com/a/b/releases/tag/v1.2.3'}
            return [base, dict(base, tag_name='v2.0.0', prerelease=True), dict(base, tag_name='v3.0.0', draft=True), dict(base, tag_name='unversioned')]
    rows = release_records(API(), {'repo': 'a/b', 'release_pattern': r'v(?P<version>\d+\.\d+\.\d+)'})
    assert len(rows) == 1 and rows[0]['version'] == '1.2.3'
    assert 'repository evidence' in rows[0]['date_kind']
