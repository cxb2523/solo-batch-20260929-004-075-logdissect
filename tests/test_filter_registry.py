"""Registry contents, declared metadata and CLI option collision checks."""

from argparse import ArgumentParser

import pytest

import logdissect.filters as filters
from logdissect.filters import (Filter, FilterOption, FilterOptionError,
        add_filter_arguments, build_plan, ordered_filters, register)


EXPECTED_FILTERS = {'last', 'range', 'grep', 'rgrep', 'source', 'rsource',
        'shost', 'rshost', 'dhost', 'rdhost', 'process', 'rprocess',
        'protocol', 'rprotocol'}


def test_all_filters_registered():
    assert set(filters.registry) == EXPECTED_FILTERS


def test_every_declared_filter_is_in_registry():
    for name in filters.__filters__:
        assert name in filters.registry


def test_filters_self_report_metadata():
    for name, filter_cls in filters.registry.items():
        assert filter_cls.name == name
        assert filter_cls.desc
        assert filter_cls.options, name
        for option in filter_cls.options:
            assert option.long_flags
            assert option.dest
            assert option.kind in filters.VALUE_KINDS
        assert isinstance(filter_cls.required_fields, tuple)
        assert isinstance(filter_cls.stateful, bool)


def test_static_priority_order_bands():
    order = [name for name, _ in ordered_filters()]
    # Stateful time windows first, content next, positive attributes,
    # reverse exclusions last.
    assert order.index('last') < order.index('range')
    assert order.index('range') < order.index('grep')
    assert order.index('grep') < order.index('source')
    assert order.index('source') < order.index('rgrep')
    assert order.index('shost') < order.index('rshost')


def test_reverse_filters_are_independent_band():
    # Reverse filters do not declare a dependency on the positive
    # filter's output: they read the same entry fields directly.
    for name in ('rgrep', 'rshost', 'rsource', 'rdhost', 'rprocess',
            'rprotocol'):
        assert filters.registry[name].priority == 40


def test_stateful_flags():
    assert filters.registry['last'].stateful is True
    assert filters.registry['range'].stateful is True
    assert filters.registry['grep'].stateful is False


def test_legacy_constructor_still_adds_arguments():
    parser = ArgumentParser()
    group = parser.add_argument_group('filter options')
    filters.registry['grep'](args=group)
    options = parser.parse_args(['--grep', 'foo'])
    assert options.pattern == ['foo']


def test_generated_parser_accepts_legacy_flags():
    parser = ArgumentParser()
    add_filter_arguments(parser)
    args = parser.parse_args([
        '--grep', 'foo', '--grep', 'bar',
        '--range', '20180101-20181231', '--utc',
        '--rgrep', 'baz', '--shost', 'host1'])
    assert args.pattern == ['foo', 'bar']
    assert args.range == '20180101-20181231'
    assert args.utc is True
    assert args.rpattern == ['baz']
    assert args.shost == ['host1']


def test_short_option_collision_raises():
    class First(Filter):
        name = 'optcoll1'
        priority = 99
        options = [FilterOption('--cc-one', '-c', dest='cc1',
                kind='value')]

    class Second(Filter):
        name = 'optcoll2'
        priority = 99
        options = [FilterOption('--cc-two', '-c', dest='cc2',
                kind='value')]

    register(First)
    register(Second)
    parser = ArgumentParser()
    with pytest.raises(FilterOptionError, match='-c'):
        add_filter_arguments(parser, filter_names=['optcoll1', 'optcoll2'])


def test_reserved_core_short_option_raises():
    class Stealer(Filter):
        name = 'optcoll3'
        priority = 99
        options = [FilterOption('--cc-three', '-s', dest='cc3',
                kind='value')]

    register(Stealer)
    parser = ArgumentParser()
    with pytest.raises(FilterOptionError, match='core'):
        add_filter_arguments(parser, filter_names=['optcoll3'])


def test_duplicate_long_option_raises():
    class Dup(Filter):
        name = 'optcoll4'
        priority = 99
        options = [FilterOption('--grep', dest='cc4', kind='value')]

    register(Dup)
    parser = ArgumentParser()
    with pytest.raises(FilterOptionError, match='--grep'):
        add_filter_arguments(parser, filter_names=['grep', 'optcoll4'])


def test_build_plan_reports_active_and_fields():
    plan = build_plan({'pattern': ['software']})
    by_name = {item['name']: item for item in plan}
    assert by_name['grep']['active'] is True
    assert by_name['grep']['active_value'] == ['software']
    assert by_name['grep']['required_fields'] == ('raw_text',)
    assert by_name['range']['active'] is False
    assert [item['name'] for item in plan] == \
            [name for name, _ in ordered_filters()]
