from logging_stats.config import load
from logging_stats.store import Store
from logging_stats.collect import run


def test_interrupted_mail_collection_resumes_at_unfinished_month(tmp_path, monkeypatch):
    import logging_stats.collect as collector
    config = load('config/commons.yaml')
    config['history_months'] = 2
    store = Store(tmp_path)
    calls = []
    def interrupted(config, months):
        calls.extend(months)
        if months == ['2026-10']:
            raise TimeoutError()
        return [{'id': months[0], 'at': months[0]+'-02T00:00:00Z', 'actor': 'synthetic'}]
    monkeypatch.setattr(collector, 'mail_records', interrupted)
    run(None, store, config, '2026-11-17T00:00:00Z', '2026-09-01T00:00:00Z', budget_projects=[])
    assert store.state['commons:mail']['status'] == 'failed'
    assert store.state['commons:mail']['coverage_months'] == ['2026-09']
    assert len(store.get('commons:mail')) == 1
    calls.clear()
    def recovered(config, months):
        calls.extend(months)
        return [{'id': months[0], 'at': months[0]+'-02T00:00:00Z', 'actor': 'synthetic'}]
    monkeypatch.setattr(collector, 'mail_records', recovered)
    run(None, store, config, '2026-11-17T00:00:00Z', '2026-09-01T00:00:00Z', budget_projects=[])
    assert calls == ['2026-10', '2026-11']
    assert store.state['commons:mail']['status'] == 'complete'
    assert store.state['commons:mail']['coverage_months'] == ['2026-09','2026-10','2026-11']
    assert len(store.get('commons:mail')) == 3
