"""The same config must yield identical output via CLI and library call."""

import os
import subprocess
import sys

from logdissect.core import LogDissectCore


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'logdissect.py')
FILES = [os.path.join(ROOT, 'tests', 'files', 'exsyslog'),
        os.path.join(ROOT, 'tests', 'files', 'exmeslog')]


def run_cli(argv):
    env = dict(os.environ)
    env['PYTHONPATH'] = ROOT + os.pathsep + env.get('PYTHONPATH', '')
    proc = subprocess.run(
            [sys.executable, '-W', 'ignore', SCRIPT] + argv,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, env=env, universal_newlines=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def run_library(config, files=None):
    core = LogDissectCore()
    config = dict(config)
    config['silentmode'] = True
    core.run_job(config=config, files=files or FILES)
    return '\n'.join(entry['raw_text']
            for entry in core.data_set['finalized_data']['entries']) + \
            ('\n' if core.data_set['finalized_data']['entries'] else '')


CONFIGS = [
    (['--grep', 'software'], {'grep': 'software'}),
    (['--grep', 'software', '--rgrep', 'dbus'],
            {'grep': ['software'], 'rgrep': ['dbus']}),
    (['--grep', 'software', '--grep', 'GNOME'],
            {'grep': ['software', 'GNOME']}),
    (['--process', 'systemd'], {'process': 'systemd'}),
    (['--source', 'shade'], {'source': 'shade'}),
    (['--source', 'shade', '--rprocess', 'dbus'],
            {'source': 'shade', 'rprocess': 'dbus'}),
    (['--range', '20260227213000-20260227213500'],
            {'range': '20260227213000-20260227213500'}),
]


def test_parity_cases():
    for argv, config in CONFIGS:
        cli_out = run_cli(argv + FILES)
        lib_out = run_library(config)
        assert cli_out == lib_out, (
                'CLI/library mismatch for %r\n--- CLI ---\n%s\n'
                '--- library ---\n%s' % (argv, cli_out, lib_out))


def test_dest_name_config_alias_equivalent():
    """Config may use argparse dest names (pattern=) too."""
    by_flag = run_library({'grep': 'software'})
    by_dest = run_library({'pattern': 'software'})
    assert by_flag == by_dest


def test_filter_plan_flag_prints_pipeline():
    out = run_cli(['--filter-plan'])
    assert 'Filter pipeline:' in out
    assert 'grep' in out
    assert '--range' in out


def test_filter_plan_shows_active_filters():
    out = run_cli(['--filter-plan', '--grep', 'software'])
    grep_line = [line for line in out.splitlines()
            if '. grep (priority' in line]
    assert len(grep_line) == 1
    assert '[active]' in grep_line[0]
    rgrep_line = [line for line in out.splitlines()
            if '. rgrep (priority' in line][0]
    assert '[inactive]' in rgrep_line


def test_no_filter_config_matches_cli():
    cli_out = run_cli(FILES)
    lib_out = run_library({})
    assert cli_out == lib_out
