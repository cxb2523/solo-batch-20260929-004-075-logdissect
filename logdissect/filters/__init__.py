# MIT License
#
# Copyright (c) 2017 Dan Persons <dpersonsdev@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Registry based filter pipeline.

Each filter module subclasses :class:`Filter` and is automatically added
to :data:`registry` when its module is imported.  Filters declare their
CLI options, value types, required entry fields and execution priority
instead of scattering that knowledge across the core.

Execution order is a *static priority* ordering, not a runtime
topological sort: the reverse filters (``rgrep``, ``rshost`` ...) are
standalone exclusion predicates on the same fields as their positive
counterparts, so they neither consume another filter's output nor feed
one, and a chain of per-entry predicates is order independent.  Static
ordering keeps ``--filter-plan`` deterministic and human readable.
"""


__filters__ = ['last', 'range', 'grep', 'rgrep', 'source', 'rsource',
        'shost', 'rshost', 'dhost', 'rdhost', 'process', 'rprocess',
        'protocol', 'rprotocol']


class FilterError(Exception):
    """Base class for filter registry errors."""


class FilterOptionError(FilterError):
    """Raised when a filter declares a conflicting CLI option."""


# Value kinds understood by the registry.  They mirror argparse actions:
# 'list'  -> action='append' (a list of strings)
# 'value' -> action='store' (a single string)
# 'flag'  -> action='store_true' (a boolean)
VALUE_KINDS = ('list', 'value', 'flag')


class FilterOption(object):
    """Declarative description of one CLI option owned by a filter."""

    def __init__(self, *flags, **attrs):
        if not flags:
            raise FilterOptionError('a filter option needs at least one flag')
        long_flags = [f for f in flags if f.startswith('--')]
        short_flags = [f for f in flags if f.startswith('-')
                and not f.startswith('--')]
        if 'dest' not in attrs or not long_flags:
            raise FilterOptionError(
                    'filter option {} needs a long flag and dest'.format(
                        flags))
        self.flags = tuple(flags)
        self.long_flags = tuple(long_flags)
        self.short_flags = tuple(short_flags)
        self.dest = attrs['dest']
        self.action = attrs.get('action', 'store')
        self.kind = attrs.get('kind')
        if self.kind is None:
            self.kind = {'append': 'list', 'store': 'value',
                    'store_true': 'flag'}[self.action]
        if self.kind not in VALUE_KINDS:
            raise FilterOptionError(
                    'unknown value kind {!r} for {}'.format(
                        self.kind, self.long_flags[0]))
        self.help_text = attrs.get('help', None)
        self.metavar = attrs.get('metavar', None)
        self.default = attrs.get('default',
                False if self.action == 'store_true' else None)
        # Store flags never activate a filter by themselves; the first
        # non-flag option of a filter is its trigger unless overridden.
        self.activates = attrs.get('activates',
                self.action != 'store_true')

    def add_to_parser(self, parser):
        """Register this option on an argparse parser/group."""
        kwargs = {'action': self.action, 'dest': self.dest,
                'default': self.default}
        if self.help_text is not None:
            kwargs['help'] = self.help_text
        if self.metavar is not None:
            kwargs['metavar'] = self.metavar
        parser.add_argument(*self.flags, **kwargs)


class Filter(object):
    """Base class for registered filter modules.

    Subclasses set :attr:`name`, :attr:`desc`, :attr:`options`,
    :attr:`required_fields`, :attr:`stateful` and :attr:`priority`, and
    implement :meth:`filter_data`.  ``options`` holds
    :class:`FilterOption` instances.
    """

    name = None
    desc = ''
    options = []
    #: Entry fields this filter inspects.
    required_fields = ('raw_text',)
    #: True for filters that window the whole (merged, sorted) stream,
    #: e.g. time range / last-N filters.
    stateful = False
    #: Smaller runs earlier.  Bands: 10 time window filters, 20 content
    #: filters, 30 positive attribute filters, 40 reverse filters.
    priority = 50

    def __init__(self, args=None):
        self.options = [o for o in type(self).options]
        if args is not None:
            # Backwards compatible hook: historically a filter module
            # registered its own argparse arguments when instantiated
            # with the filter argument group.
            for option in self.options:
                option.add_to_parser(args)

    def filter_data(self, data, values=None, args=None, **kwargs):
        """Filter a merged log dict and return a new log dict."""
        raise NotImplementedError

    def is_active(self, config):
        """Return the configured value when this filter should run."""
        for option in self.options:
            if not option.activates:
                continue
            value = _config_value(config, option.dest)
            if value not in (None, False, [], ''):
                return value
        return None

    @staticmethod
    def copy_meta(source, target):
        """Copy per-file metadata keys onto a rebuilt log dict."""
        for key in ('parser', 'source_path', 'source_file',
                'source_file_mtime', 'source_file_year'):
            if key in source:
                target[key] = source[key]
        return target


registry = {}


def register(filter_cls):
    """Class decorator that inserts a filter into the registry."""
    if not getattr(filter_cls, 'name', None):
        raise FilterOptionError(
                '{} has no filter name'.format(filter_cls.__name__))
    if filter_cls.name in registry and \
            registry[filter_cls.name] is not filter_cls:
        raise FilterOptionError(
                'duplicate filter name {!r}'.format(filter_cls.name))
    registry[filter_cls.name] = filter_cls
    return filter_cls


def ordered_filters(names=None):
    """Return (name, class) pairs in static execution order."""
    items = list(registry.items())
    if names is not None:
        items = [(n, c) for n, c in items if n in names]
    return sorted(items, key=lambda item: (item[1].priority, item[0]))


# Short flags owned by the core argument parser; filters may not steal
# these.  -h is reserved automatically by argparse.
RESERVED_SHORT_OPTIONS = ('h', 's', 'p', 'z', 't')


def add_filter_arguments(parser, filter_names=None, reserved_shorts=None):
    """Add all registered filter options to an argparse parser/group.

    Raises :class:`FilterOptionError` on duplicate long flags, duplicate
    short flags, or collision with reserved core short flags.
    """
    reserved = set(RESERVED_SHORT_OPTIONS if reserved_shorts is None
            else reserved_shorts)
    seen_long = set()
    seen_short = set(reserved)
    # CLI construction order is alphabetical by filter name (the
    # historical load order), with each filter's own options emitted
    # in declaration order, so that --utc stays next to --range and
    # --help output remains stable.
    names = sorted(__filters__) if filter_names is None \
            else sorted(filter_names)
    for name in names:
        filter_cls = registry[name]
        for option in filter_cls.options:
            for flag in option.long_flags:
                if flag in seen_long:
                    raise FilterOptionError(
                            'duplicate long option {} from filter '
                            '{!r}'.format(flag, name))
                seen_long.add(flag)
            for flag in option.short_flags:
                short = flag.lstrip('-')
                if short in seen_short:
                    raise FilterOptionError(
                            'short option {} from filter {!r} collides '
                            'with a {}'.format(
                                flag, name,
                                'reserved core option' if short in reserved
                                else 'option registered by another filter'))
                seen_short.add(short)
            option.add_to_parser(parser)


def _config_value(config, dest):
    if config is None:
        return None
    if hasattr(config, dest):
        return getattr(config, dest)
    try:
        return config[dest]
    except (KeyError, TypeError):
        return None


def build_plan(config=None, filter_names=None):
    """Describe the pipeline for *config*.

    Returns a list of dicts in static execution order.  Each entry
    carries the filter metadata and whether/with what value it is
    active.
    """
    plan = []
    for name, filter_cls in ordered_filters(filter_names):
        instance = filter_cls()
        active = instance.is_active(config) if config is not None else None
        plan.append({
            'name': name,
            'desc': filter_cls.desc,
            'priority': filter_cls.priority,
            'stateful': filter_cls.stateful,
            'required_fields': tuple(filter_cls.required_fields),
            'options': tuple(instance.options),
            'active_value': active,
            'active': active not in (None, False, [], ''),
            })
    return plan


def run_pipeline(data, config=None, filter_names=None, instances=None):
    """Run the active registered filters over one merged log dict.

    ``data`` is the fully merged, time sorted stream, so stateful
    filters (``range``/``last``) evaluate one global window -- the same
    grouping used by the CLI path and the library path.

    ``config`` may be an argparse namespace or a plain dict.  Returns
    the filtered log dict.
    """
    if config is None:
        return data
    if instances is None:
        instances = {}
    current = data
    for name, filter_cls in ordered_filters(filter_names):
        ourfilter = instances.get(name, filter_cls())
        trigger = None
        kwargs = {}
        for option in ourfilter.options:
            value = _config_value(config, option.dest)
            if option.activates and value not in (None, False, [], ''):
                if trigger is None:
                    trigger = value
                if option.kind == 'value':
                    kwargs['value'] = value
                elif option.kind == 'list':
                    kwargs.setdefault('values', []).extend(value)
            elif option.kind == 'flag':
                kwargs[option.dest] = bool(value)
        if trigger is None:
            continue
        current = ourfilter.filter_data(current, args=None, **kwargs)
    return current


import logdissect.filters.last
import logdissect.filters.range
import logdissect.filters.grep
import logdissect.filters.rgrep
import logdissect.filters.source
import logdissect.filters.rsource
import logdissect.filters.shost
import logdissect.filters.rshost
import logdissect.filters.dhost
import logdissect.filters.rdhost
import logdissect.filters.process
import logdissect.filters.rprocess
import logdissect.filters.protocol
import logdissect.filters.rprotocol
