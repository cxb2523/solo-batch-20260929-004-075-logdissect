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

"""Registry-based filter pipeline for logdissect.

Filters self-describe their CLI options (short/long flags, value type,
metavar, help text), the entry fields they depend on, and a static
execution priority.  :class:`FilterRegistry` collects them, generates the
argparse options, checks short-option collisions, and builds a
deterministic execution plan.

Design notes
------------
* Ordering uses *static priorities*, not a runtime topological sort:
  every filter is a pure predicate over a single entry, so no filter
  consumes fields another filter produces -- there is no dependency edge
  to sort.  Reverse filters (``rgrep``/``rshost``/...) are simple
  exclusion predicates and commute with the positive matchers; they run
  in the final band purely as a documented convention.
* ``range`` and ``last`` are :attr:`Filter.stateful` (they select by
  timestamp, which is meaningless for a partially observed stream), so
  under streaming input entries are grouped and the stateful filters see
  each completed group -- the same whole-group data set a library call
  with the same config receives.
"""

from copy import copy

from logdissect.filters.type import Filter, FilterModule, OptionSpec


class FilterRegistrationError(Exception):
    """Raised when two registered filters claim the same option."""
    pass


def field_filter_data(data, values, field, exclude=False):
    """Shared predicate for the single-field match/exclude filters.

    ``exclude=False`` keeps entries whose ``field`` is in ``values``
    (entries without the field are dropped); ``exclude=True`` drops
    matching entries and keeps everything else, including entries that
    lack the field -- identical semantics for CLI and library calls.
    """
    newdata = {}
    for key in ('parser', 'source_path', 'source_file',
            'source_file_mtime', 'source_file_year'):
        if key in data:
            newdata[key] = data[key]
    newdata['entries'] = []
    for entry in data['entries']:
        present = field in entry
        matched = present and entry[field] in values
        if (not exclude and matched) or (exclude and not matched):
            newdata['entries'].append(entry)
    return newdata


# Short flags owned by the core parser -- filters may never claim these.
RESERVED_SHORT_OPTIONS = set(['-h', '-s', '-p', '-z', '-t', '-v'])


class FilterRegistry(object):
    """Collects filter classes and builds the pipeline/CLI metadata."""

    def __init__(self):
        self._filters = {}
        self._short_owners = dict((opt, '<core>')
                for opt in RESERVED_SHORT_OPTIONS)
        self._long_owners = {}
        self._dest_owners = {}

    def register(self, filter_cls):
        """Register a :class:`Filter` subclass (returns it)."""
        instance = filter_cls()
        name = instance.name or filter_cls.__name__
        if not instance.name:
            instance.name = name
        if name in self._filters:
            raise FilterRegistrationError(
                    "duplicate filter name: %s" % name)
        for spec in instance.options:
            if spec.long_flag in self._long_owners:
                raise FilterRegistrationError(
                        "long option %s claimed by both '%s' and '%s'" %
                        (spec.long_flag, self._long_owners[spec.long_flag],
                            name))
            self._long_owners[spec.long_flag] = name
            if spec.short_flag:
                if spec.short_flag in self._short_owners:
                    raise FilterRegistrationError(
                            "short option %s claimed by both '%s' and '%s'"
                            % (spec.short_flag,
                                self._short_owners[spec.short_flag], name))
                self._short_owners[spec.short_flag] = name
            if spec.dest in self._dest_owners and spec.activates:
                raise FilterRegistrationError(
                        "destination %s claimed by both '%s' and '%s'" %
                        (spec.dest, self._dest_owners[spec.dest], name))
            self._dest_owners[spec.dest] = name
        self._filters[name] = instance
        return filter_cls

    def unregister(self, name):
        """Remove a filter (used by tests that install fakes)."""
        instance = self._filters.pop(name, None)
        if instance is None:
            return
        for spec in instance.options:
            self._long_owners.pop(spec.long_flag, None)
            self._short_owners.pop(spec.short_flag, None)
            self._dest_owners.pop(spec.dest, None)

    def names(self):
        return list(self._filters.keys())

    def get(self, name):
        return self._filters[name]

    def all(self):
        """All registered filter instances."""
        return list(self._filters.values())

    def options(self):
        """All option specs in module-name order."""
        specs = []
        for name in sorted(self._filters):
            specs.extend(self._filters[name].options)
        return specs

    def add_arguments(self, group, reserved_short=None):
        """Generate argparse arguments from registered filters.

        Raises :class:`FilterRegistrationError` on any collision with
        core reserved short options or another registered filter.
        """
        claimed = dict((opt, '<core>') for opt in
                (reserved_short or RESERVED_SHORT_OPTIONS))
        for spec in self.options():
            if spec.short_flag and spec.short_flag in claimed:
                raise FilterRegistrationError(
                        "short option %s collision: claimed by both "
                        "'%s' and '%s'" % (spec.short_flag,
                            claimed[spec.short_flag],
                            self._long_owners[spec.long_flag]))
            kwargs = dict(action=spec.action, dest=spec.dest,
                    help=spec.help)
            if spec.action in ('store', 'append'):
                kwargs['type'] = spec.type
                if spec.metavar:
                    kwargs['metavar'] = spec.metavar
            else:
                kwargs['default'] = spec.default
            group.add_argument(*spec.flags, **kwargs)
            if spec.short_flag:
                claimed[spec.short_flag] = \
                        self._long_owners[spec.long_flag]

    def build_plan(self, args=None):
        """Return the ordered list of filters to execute.

        With ``args`` given the plan is restricted to filters enabled by
        the parsed config; without args it documents the full pipeline.
        """
        if args is None:
            return sorted(self._filters.values(),
                    key=lambda f: (f.priority, f.name))
        return sorted((f for f in self._filters.values()
                if f.is_active(args)),
                key=lambda f: (f.priority, f.name))

    def build_full_plan(self):
        """The full static plan in documented (priority, name) order."""
        return sorted(self._filters.values(),
                key=lambda f: (f.priority, f.name))

    def apply_plan(self, data, args, plan=None):
        """Run an execution plan against a (whole-group) data set."""
        result = copy(data)
        for ourfilter in (plan if plan is not None
                else self.build_plan(args)):
            result = ourfilter.apply(result, args)
        return result

    def filter_stream(self, entry_groups, args, plan=None):
        """Yield filtered results for grouped streaming input.

        Stateless filters are applied per group; stateful filters
        (``range``/``last``) receive each completed group so grouping
        boundaries decide their window instead of an arbitrary chunk
        boundary.  This is the exact same code path used for a
        one-shot library call, so both produce identical results for the
        same config.
        """
        active = plan if plan is not None else self.build_plan(args)
        per_group = [f for f in active if not f.stateful]
        stateful = [f for f in active if f.stateful]
        for group in entry_groups:
            result = group
            for ourfilter in stateful + per_group:
                result = ourfilter.apply(result, args)
            yield result

    def render_plan_text(self, args=None):
        """Render ``--filter-plan`` style plain text."""
        lines = ['Filter pipeline:']
        for index, ourfilter in enumerate(self.build_full_plan(), 1):
            flags = ', '.join(self._flag_labels(ourfilter))
            fields = ', '.join(ourfilter.required_fields)
            active = '' if args is None else \
                    ' [active]' if ourfilter.is_active(args) else \
                    ' [inactive]'
            lines.append('  %d. %s (priority %d)%s' %
                    (index, ourfilter.name, ourfilter.priority, active))
            lines.append('      options : %s' % (flags or '(none)'))
            lines.append('      fields  : %s' % fields)
            kind = 'stateful (grouped under streaming input)' \
                    if ourfilter.stateful else 'stateless'
            lines.append('      kind    : %s' % kind)
        return '\n'.join(lines)

    @staticmethod
    def _flag_labels(ourfilter):
        labels = []
        for spec in ourfilter.options:
            label = spec.long_flag
            if spec.short_flag:
                label = spec.short_flag + ', ' + label
            if spec.action != 'store_true':
                label += ' ' + spec.value_name()
            labels.append(label)
        return labels


#: Process-wide registry populated as filter modules are imported.
registry = FilterRegistry()

#: Legacy module name list (import side effects populate ``registry``).
__filters__ = ['last', 'range', 'grep', 'rgrep', 'source', 'rsource',
        'shost', 'rshost', 'dhost', 'rdhost', 'process', 'rprocess',
        'protocol', 'rprotocol']

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
