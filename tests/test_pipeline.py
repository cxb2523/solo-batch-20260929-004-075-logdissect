"""Filtering semantics, stateful windows and CLI/library parity."""

import json
import subprocess
import sys

import pytest

import logdissect.filters as filters
from logdissect.core import (render_filter_plan_html, render_filter_plan_text,
        run_library_job)


def _raw(data):
    return [entry['raw_text'] for entry in data['entries']]


def test_grep_matches(sample_logs):
    result = run_library_job(sample_logs, {'pattern': ['software']})
    assert len(result['entries']) == 7
    assert all('software' in line for line in _raw(result))


def test_rgrep_excludes(sample_logs):
    result = run_library_job(sample_logs, {'rpattern': ['dbus']})
    assert all('dbus' not in line for line in _raw(result))
    full = run_library_job(sample_logs, {})
    grep = run_library_job(sample_logs, {'pattern': ['dbus']})
    # Positive and reverse filters partition the stream for this term:
    assert len(result['entries']) + len(grep['entries']) == \
        len(full['entries'])


def test_range_window(sample_logs):
    result = run_library_job(
            sample_logs, {'range': '20180202020202-20180227213200'})
    assert len(result['entries']) == 18
    for entry in result['entries']:
        assert 20180202020202 <= int(
                entry['numeric_date_stamp'].split('.')[0]) <= \
                20180227213200


def test_range_window_evaluated_once_over_merged_stream(sample_logs):
    # The same config over the merged stream must equal applying the
    # window to each file independently and concatenating: there is one
    # global window, not a per-file regrouping.
    merged = run_library_job(
            sample_logs, {'range': '20180202020202-20180227213200'})
    per_file = []
    for path in sample_logs:
        per_file.extend(run_library_job(
            [path], {'range': '20180202020202-20180227213200'})[
                'entries'])
    # Membership is identical (one global window vs per-file windows
    # of the same bounds); only the interleaving/sort order differs.
    assert sorted(_raw(merged)) == sorted(
            entry['raw_text'] for entry in per_file)


def test_attribute_filters(sample_logs):
    assert len(run_library_job(sample_logs,
        {'process': ['systemd']})['entries']) == 3
    assert len(run_library_job(sample_logs,
        {'source': ['shade']})['entries']) == 20
    assert run_library_job(sample_logs, {'rsource': ['shade']})[
            'entries'] == []


def test_last_window_recent_log(tmp_path):
    import datetime
    log = tmp_path / 'fresh.log'
    now = datetime.datetime.utcnow()
    log.write_text(now.strftime('%b %d %H:%M:%S') +
            ' shade testproc[1]: hello recent event\n')
    stamp = now.timestamp()
    import os
    os.utime(str(log), (stamp, stamp))
    result = run_library_job([str(log)], {'last': '1h'})
    assert len(result['entries']) == 1


def test_reverse_filter_composition(sample_logs):
    result = run_library_job(sample_logs,
            {'pattern': ['software'], 'rpattern': ['azuri']})
    lines = _raw(result)
    assert len(lines) == 5
    assert all('software' in line for line in lines)
    assert all('azuri' not in line for line in lines)


def test_legacy_library_module_calls(sample_logs):
    # The documented module API (filter_data with values=) still works.
    from logdissect.parsers.syslog import ParseModule
    from logdissect.filters.grep import FilterModule as Grep
    from logdissect.filters.rgrep import FilterModule as Rgrep
    parser = ParseModule()
    parsed = parser.parse_file(sample_logs[0])
    matched = Grep().filter_data(parsed, values=['software'])
    excluded = Rgrep().filter_data(matched, values=['azuri'])
    assert len(matched['entries']) == 2
    assert len(excluded['entries']) == 1
    assert 'azuri' not in excluded['entries'][0]['raw_text']


CONFIGS = [
    {'pattern': ['software']},
    {'range': '20180202020202-20180227213200'},
    {'range': '20180202020202-20180227213200', 'pattern': ['dbus']},
    {'process': ['systemd']},
    {'rpattern': ['dbus']},
    {'pattern': ['software'], 'rpattern': ['azuri']},
    {'source': ['shade']},
    {'rsource': ['shade']},
]


@pytest.mark.parametrize('config', CONFIGS)
def test_cli_and_library_give_same_output(config, sample_logs, tmp_path,
        repo_root):
    """Same config through CLI and through the library call must match."""
    library_result = run_library_job(sample_logs, config)

    cli_out = tmp_path / 'cli.json'
    cli_args = [sys.executable, 'logdissect.py', '-s',
            '--sojson', str(cli_out)]
    for value in config.get('pattern', []):
        cli_args += ['--grep', value]
    for value in config.get('rpattern', []):
        cli_args += ['--rgrep', value]
    for value in config.get('process', []):
        cli_args += ['--process', value]
    for value in config.get('source', []):
        cli_args += ['--source', value]
    for value in config.get('rsource', []):
        cli_args += ['--rsource', value]
    if 'range' in config:
        cli_args += ['--range', config['range']]
    cli_args += sample_logs
    subprocess.run(cli_args, cwd=repo_root, check=True)

    cli_lines = [entry['raw_text']
            for entry in json.load(open(str(cli_out)))]
    assert cli_lines == _raw(library_result)


def test_filter_plan_cli(repo_root):
    proc = subprocess.run(
            [sys.executable, 'logdissect.py', '--filter-plan'],
            cwd=repo_root, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True)
    assert proc.returncode == 0
    assert 'Filter pipeline plan' in proc.stdout
    assert 'grep' in proc.stdout and 'rshost' in proc.stdout
    assert 'numeric_date_stamp' in proc.stdout
    assert 'priority' in proc.stdout


def test_filter_plan_text_and_html():
    text = render_filter_plan_text({'pattern': ['software']})
    assert '1.' in text and '[ACTIVE] grep' in text
    html = render_filter_plan_html({'range': '20180101-20181231'})
    assert '<html' in html and '</html>' in html
    assert '<th>Filter</th>' in html
    assert 'stateful' in html
    assert '--grep' in html and 'raw_text' in html
    assert 'rshost' in html
    # Active range row is marked, and its configured value appears.
    assert 'tr class="active"' in html
    assert '20180101-20181231' in html
