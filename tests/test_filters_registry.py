import pytest

from argparse import ArgumentParser

from logdissect.filters import registry
from logdissect.filters import FilterRegistrationError
from logdissect.filters.type import Filter, OptionSpec


FILTER_NAMES = ['last', 'range', 'grep', 'rgrep', 'source', 'rsource',
        'shost', 'rshost', 'dhost', 'rdhost', 'process', 'rprocess',
        'protocol', 'rprotocol']


def test_all_filters_registered():
    assert sorted(registry.names()) == sorted(FILTER_NAMES)


def test_legacy_flags_and_help_preserved():
    by_flag = dict((spec.long_flag, spec)
            for spec in registry.options())
    assert by_flag['--grep'].help == 'match a pattern'
    assert by_flag['--grep'].metavar == 'PATTERN'
    assert by_flag['--grep'].action == 'append'
    assert by_flag['--grep'].dest == 'pattern'
    assert by_flag['--range'].help == \
            'match a time range (YYYYMMDDhhmm-YYYYMMDDhhmm)'
    assert by_flag['--range'].action == 'store'
    assert by_flag['--rgrep'].metavar == 'PATTERN'
    assert by_flag['--rshost'].metavar == 'SHOST'
    assert by_flag['--rsource'].metavar == 'SOURCE'
    assert by_flag['--utc'].action == 'store_true'


def test_generated_argparse_accepts_legacy_flags():
    parser = ArgumentParser()
    group = parser.add_argument_group('filter options')
    registry.add_arguments(group)
    args = parser.parse_args(
            ['--grep', 'foo', '--grep', 'bar', '--range',
                '20160101-20170101', '--shost', 'host1'])
    assert args.pattern == ['foo', 'bar']
    assert args.range == '20160101-20170101'
    assert args.shost == ['host1']
    assert args.utc is False


def test_new_short_options_work():
    parser = ArgumentParser()
    group = parser.add_argument_group('filter options')
    registry.add_arguments(group)
    args = parser.parse_args(
            ['-g', 'foo', '-G', 'bar', '-L', '10m', '-R',
                '20160101-20170101'])
    assert args.pattern == ['foo']
    assert args.rpattern == ['bar']
    assert args.last == '10m'
    assert args.range == '20160101-20170101'


def test_short_option_collision_raises():
    class Collider(Filter):
        def __init__(self, args=None):
            self.name = 'collider-x'
            self.desc = 'claims a core short flag'
            self.options = [
                OptionSpec('--collider-x', dest='collider_x',
                        action='append', type=str, short_flag='-s',
                        help='x'),
            ]

    with pytest.raises(FilterRegistrationError):
        registry.register(Collider)
    assert 'collider-x' not in registry.names()


def test_short_option_collision_between_filters_raises():
    class First(Filter):
        def __init__(self, args=None):
            self.name = 'fake-first'
            self.desc = 'first'
            self.options = [
                OptionSpec('--fake-first', dest='fake_first',
                        short_flag='-9', help='first'),
            ]

    class Second(Filter):
        def __init__(self, args=None):
            self.name = 'fake-second'
            self.desc = 'second'
            self.options = [
                OptionSpec('--fake-second', dest='fake_second',
                        short_flag='-9', help='second'),
            ]

    registry.register(First)
    try:
        with pytest.raises(FilterRegistrationError):
            registry.register(Second)
        assert 'fake-second' not in registry.names()
    finally:
        registry.unregister('fake-first')


def test_duplicate_long_flag_raises():
    class Dup(Filter):
        def __init__(self, args=None):
            self.name = 'fake-dup-grep'
            self.desc = 'duplicates --grep'
            self.options = [
                OptionSpec('--grep', dest='fake_dup',
                        action='append', help='dup'),
            ]

    with pytest.raises(FilterRegistrationError):
        registry.register(Dup)


def test_static_plan_order():
    names = [f.name for f in registry.build_plan()]
    assert names.index('last') < names.index('range')
    assert names.index('range') < names.index('grep')
    assert names.index('grep') < names.index('rgrep')
    assert names.index('source') < names.index('rsource')
    assert names.index('shost') < names.index('rshost')


def test_active_plan_only_contains_enabled_filters():
    parser = ArgumentParser()
    registry.add_arguments(parser.add_argument_group('filters'))
    args = parser.parse_args(['--grep', 'x', '--rgrep', 'y'])
    names = [f.name for f in registry.build_plan(args)]
    assert names == ['grep', 'rgrep']


def test_stateful_and_dependency_metadata():
    assert registry.get('range').stateful is True
    assert registry.get('last').stateful is True
    assert registry.get('grep').stateful is False
    assert 'numeric_date_stamp' in registry.get('range').required_fields
    assert registry.get('rgrep').required_fields == ['raw_text']
    assert registry.get('source').required_fields == ['log_source']


def test_render_plan_text_documents_pipeline():
    text = registry.render_plan_text()
    assert 'Filter pipeline:' in text
    assert 'last' in text and 'range' in text
    assert '--grep PATTERN' in text
    assert 'priority' in text
