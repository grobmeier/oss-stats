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
from datetime import timedelta

import pytest

from oss_stats.metrics import AGE_BUCKETS, calculate
from oss_stats.timeutil import norm_ts, parse_ts

START = '2026-01-01T00:00:00Z'
END = '2026-02-01T00:00:00Z'
AS_OF = '2026-05-01T00:00:00Z'


def item(id='first', actor='new-person', created=START, **changes):
    return dict({'id': id, 'actor': actor, 'created_at': created, 'state': 'open', 'history': 'events',
                 'draft': False, 'title': 'PR', 'url': 'https://github.com/a/b/pull/1', 'updated_at': created, 'events': [], 'comments': [], 'reviews': []}, **changes)


def metric(rows, name, at=AS_OF, floor=1):
    return calculate({'pulls': rows}, START, END, floor=floor, observed_until=at)['newcomer_' + name]


def test_cohort_outcomes_use_report_horizon_after_cohort_period_end():
    rows = [item(comments=[{'actor': 'maintainer', 'at': '2026-01-31T00:00:00Z'}], merged_at='2026-03-01T00:00:00Z'),
            item('return', created='2026-03-15T00:00:00Z')]
    for name in ('pr_authors', 'response_eligible', 'followup_eligible', 'responded', 'merged', 'returned'):
        assert metric(rows, name)['value'] == 1
    for name in ('response_share', 'merge_share', 'return_share'):
        assert metric(rows, name)['value'] == 1
    # Merge remains outside January's ordinary work-flow totals.
    assert calculate({'pulls': rows}, START, END, observed_until=AS_OF)['prs_merged']['value'] == 0


def test_incomplete_windows_are_not_failures_and_rates_obey_floor():
    rows = [item()]
    result = metric(rows, 'return_share', at=END)
    assert result['value'] is None and result['n'] == 0
    assert 'fully observed' in result['reason']
    result = metric(rows, 'return_share', floor=5)
    assert result['value'] is None and result['n'] == 1 and result['status'] == 'insufficient data'


def test_bots_self_responses_and_late_outcomes_are_excluded():
    rows = [item(comments=[{'actor': None, 'at': START}, {'actor': 'new-person', 'at': START},
                           {'actor': 'other', 'at': '2026-02-01T00:00:00Z'}], merged_at='2026-04-02T00:00:00Z'),
            item('return', created='2026-04-02T00:00:00Z'), item('bot', actor=None)]
    assert metric(rows, 'pr_authors')['value'] == 1
    for name in ('responded', 'merged', 'returned'):
        assert metric(rows, name)['value'] == 0


def test_reviews_count_as_response_and_prior_authors_are_not_new():
    rows = [item(reviews=[{'actor': 'reviewer', 'at': START}]),
            item('old-first', actor='old', created='2025-12-01T00:00:00Z'), item('old-again', actor='old')]
    assert metric(rows, 'pr_authors')['value'] == 1
    assert metric(rows, 'responded')['value'] == 1


def test_outcome_deadline_is_inclusive_but_report_timestamp_is_exclusive():
    rows = [item(merged_at='2026-04-01T00:00:00Z'), item('return', created='2026-04-01T00:00:00Z')]
    assert metric(rows, 'merged')['value'] == 1
    assert metric(rows, 'returned')['value'] == 1
    assert metric(rows, 'followup_eligible', at='2026-04-01T00:00:00Z')['value'] == 0


@pytest.mark.parametrize('kind,prefix', [('pulls','pr'), ('issues','issue')])
def test_age_buckets_are_disjoint_and_partition_backlog(kind, prefix):
    ages = [0.5, 7, 29.9, 30, 89.9, 90, 200]
    rows = [item(str(i), created=norm_ts((parse_ts(END)-timedelta(days=age)).isoformat())) for i, age in enumerate(ages)]
    rows += [item('closed', closed_at=START), item('draft', draft=kind == 'pulls', closed_at=START if kind == 'issues' else None)]
    result = calculate({kind: rows}, START, END)
    counts = [result[prefix+'_backlog_age_'+key]['value'] for key, *_ in AGE_BUCKETS]
    assert counts == [1, 2, 2, 2]
    assert sum(counts) == result[prefix+'_backlog']['value']


def test_quarterly_cohorts_use_unique_authors_and_original_outcomes():
    rows = [item(), item('same-author', created='2026-02-01T00:00:00Z'),
            item('second-author', actor='another', created='2026-02-01T00:00:00Z')]
    result = calculate({'pulls': rows}, START, '2026-04-01T00:00:00Z', floor=1, observed_until='2026-06-01T00:00:00Z')
    assert result['newcomer_pr_authors']['value'] == 2
    assert result['newcomer_followup_eligible']['value'] == 2
    assert result['newcomer_return_share']['value'] == .5


def test_report_journey_is_shared_by_catalogues_and_ignores_module_filter(tmp_path):
    from oss_stats.config import load
    from oss_stats.metrics import build_report
    from oss_stats.store import Store
    config = load()
    config['history_months'] = 5
    store = Store(tmp_path)
    # A human first contributes in one repository and returns in another.
    store.save('log4j:pulls', [item(modules=['API'])], {'status': 'complete'})
    store.save('kotlin:pulls', [item('return', created='2026-02-01T00:00:00Z')], {'status': 'complete'})
    report = build_report(store, config, '2026-06-01T00:00:00Z')
    def find(scope, metric):
        return next(r for r in report['metrics'] if r['scope'] == scope and r['metric'] == metric and r['grouping'] == 'monthly' and r['start'] == START)
    assert find('logging', 'newcomer_pr_authors')['value'] == 1
    assert find('logging', 'newcomer_returned')['value'] == 1
    assert find('log4j', 'newcomer_returned')['value'] == 0
    assert not any(r['scope'] == 'log4j/API' and r['metric'].startswith('newcomer_') for r in report['metrics'])
    assert find('logging', 'newcomer_returned')['status'] == 'partial'  # Other repositories are not collected.
