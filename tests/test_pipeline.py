from types import SimpleNamespace

from logdissect.filters import registry
from logdissect.parsers.syslog import ParseModule
from logdissect.utils import merge_logs


SAMPLE = {
    'entries': [
        {'raw_text': 'host-a alpha one', 'log_source': 'host-a',
            'source_process': 'sshd',
            'numeric_date_stamp': '20200101000000',
            'numeric_date_stamp_utc': '20200101000000'},
        {'raw_text': 'host-b alpha two', 'log_source': 'host-b',
            'source_process': 'systemd',
            'numeric_date_stamp': '20200102000000',
            'numeric_date_stamp_utc': '20200102000000'},
        {'raw_text': 'host-a beta three', 'log_source': 'host-a',
            'source_process': 'cron',
            'numeric_date_stamp': '20200103000000',
            'numeric_date_stamp_utc': '20200103000000'},
    ]
}


def _args(**kwargs):
    defaults = dict(pattern=None, rpattern=None, source=None,
            rsource=None, shost=None, rshost=None, dhost=None,
            rdhost=None, process=None, rprocess=None, protocol=None,
            rprotocol=None, last=None, range=None, utc=False)
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _raw(data):
    return [entry['raw_text'] for entry in data['entries']]


def test_grep_or_semantics():
    data = registry.get('grep').filter_data(
            SAMPLE, values=['alpha', 'beta'])
    assert _raw(data) == [
            'host-a alpha one', 'host-b alpha two',
            'host-a beta three']


def test_rgrep_drops_any_match_without_args():
    data = registry.get('rgrep').filter_data(
            SAMPLE, values=['alpha'])
    assert _raw(data) == ['host-a beta three']


def test_rgrep_multiple_patterns():
    data = registry.get('rgrep').filter_data(
            SAMPLE, values=['alpha', 'beta'])
    assert _raw(data) == []


def test_rsource_library_without_args():
    data = registry.get('rsource').filter_data(
            SAMPLE, values=['host-a'])
    assert _raw(data) == ['host-b alpha two']


def test_reverse_filter_keeps_entries_without_field():
    sample = {'entries': [
        {'raw_text': 'no field here'},
        {'raw_text': 'has process', 'source_process': 'sshd'}]}
    data = registry.get('rprocess').filter_data(
            sample, values=['sshd'])
    assert _raw(data) == ['no field here']


def test_positive_filter_drops_entries_without_field():
    sample = {'entries': [
        {'raw_text': 'no field here'},
        {'raw_text': 'has process', 'source_process': 'sshd'}]}
    data = registry.get('process').filter_data(
            sample, values=['sshd'])
    assert _raw(data) == ['has process']


def test_empty_values_is_noop():
    data = registry.get('grep').filter_data(SAMPLE, values=None)
    assert data is SAMPLE


def test_range_local_and_utc():
    rng = registry.get('range')
    local = rng.filter_data(
            SAMPLE, values='20200102-20200103', utc=False)
    assert _raw(local) == ['host-b alpha two', 'host-a beta three']
    utc = rng.filter_data(
            SAMPLE, values='20200102-20200103', utc=True)
    assert _raw(utc) == ['host-b alpha two', 'host-a beta three']


def test_pipeline_apply_plan_order():
    args = _args(pattern=['alpha'], rpattern=['host-b'])
    data = registry.apply_plan(SAMPLE, args)
    assert _raw(data) == ['host-a alpha one']


def test_stream_groups_match_wholeset_result():
    group1 = {'entries': SAMPLE['entries'][:2]}
    group2 = {'entries': SAMPLE['entries'][2:]}
    args = _args(pattern=['alpha'], rpattern=['host-b'])
    streamed = []
    for result in registry.filter_stream(iter([group1, group2]), args):
        streamed.extend(_raw(result))
    assert streamed == _raw(registry.apply_plan(SAMPLE, args))


def test_stateful_filter_runs_per_stream_group():
    group1 = {'entries': SAMPLE['entries'][:2]}
    group2 = {'entries': SAMPLE['entries'][2:]}
    args = _args(range='20200101-20200102')
    streamed = []
    for result in registry.filter_stream(iter([group1, group2]), args):
        streamed.extend(_raw(result))
    # Each completed group is filtered with the same range window that a
    # one-shot library call uses for the same group data.
    assert streamed == _raw(
            registry.get('range').filter_data(
                group1, values='20200101-20200102')) + \
            _raw(registry.get('range').filter_data(
                group2, values='20200101-20200102'))


def test_stream_group_identical_to_grouped_library_call():
    """Grouped streaming == library call applied to the same group."""
    group = {'entries': SAMPLE['entries']}
    args = _args(range='20200101-20200102', pattern=['alpha'])
    streamed = []
    for result in registry.filter_stream(iter([group]), args):
        streamed.extend(_raw(result))
    assert streamed == _raw(registry.apply_plan(group, args))


def test_real_parse_merge_filters():
    parser = ParseModule()
    merged = merge_logs([
            parser.parse_file('tests/files/exsyslog'),
            parser.parse_file('tests/files/exmeslog')], sort=True)
    args = _args(pattern=['software'], rpattern=['dbus'])
    result = registry.apply_plan(merged, args)
    raw = _raw(result)
    assert raw
    assert all('software' in line for line in raw)
    assert all('dbus' not in line for line in raw)
