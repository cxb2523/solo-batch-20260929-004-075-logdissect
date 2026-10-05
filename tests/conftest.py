"""Shared fixtures for the logdissect registry-pipeline test suite."""

import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TEST_FILES = os.path.join(ROOT, 'tests', 'files')


@pytest.fixture
def sample_logs(tmp_path):
    """Copy the example logs into tmp_path with a fixed 2018 mtime.

    The syslog parser derives years from file mtime, so the copies get
    a stable timestamp instead of inheriting checkout time.
    """
    import datetime
    files = []
    for name in ('exsyslog', 'exmeslog'):
        target = tmp_path / name
        shutil.copy(os.path.join(TEST_FILES, name), str(target))
        stamp = datetime.datetime(2018, 2, 27, 21, 40, 0).timestamp()
        os.utime(str(target), (stamp, stamp))
        files.append(str(target))
    return files


@pytest.fixture
def repo_root():
    return ROOT
