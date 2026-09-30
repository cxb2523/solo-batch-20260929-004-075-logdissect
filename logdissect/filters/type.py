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

"""Base class and option metadata for registered logdissect filters.

A filter declares everything the framework needs to plug it into the
CLI and the execution pipeline:

* :attr:`options` -- the argparse options it contributes (self-reported
  CLI flags, value type, metavar and help text);
* :attr:`required_fields` -- the entry fields each filter depends on;
* :attr:`priority` -- a static priority used to order the pipeline;
* :attr:`stateful` -- whether the filter carries cross-entry state and
  therefore needs a complete (grouped) data set under streaming input.

The class keeps the legacy ``FilterModule(args=...)`` /
``filter_data(data, values=, args=)`` interface so existing scripts and
library calls keep working.
"""


class OptionSpec(object):
    """Self-reported argparse option metadata for a filter."""

    def __init__(self, long_flag, dest, action='store', type=str,
            short_flag=None, metavar=None, default=None, help='',
            activates=True):
        #: Long flag, e.g. ``'--grep'``.
        self.long_flag = long_flag
        #: Short flag, e.g. ``'-g'`` (``None`` for long-only options).
        self.short_flag = short_flag
        #: argparse destination.
        self.dest = dest
        #: argparse action (``'store'``, ``'append'`` or ``'store_true'``).
        self.action = action
        #: Value type for ``store``/``append`` options.
        self.type = type
        #: Optional metavar override.
        self.metavar = metavar
        #: argparse default.
        self.default = default
        #: Help text (kept identical to the legacy flags).
        self.help = help
        #: True when a non-default value for this option enables the
        #: filter; False for modifier flags such as ``--utc``.
        self.activates = activates

    @property
    def flags(self):
        """The flag tuple handed to ``add_argument``."""
        if self.short_flag:
            return [self.short_flag, self.long_flag]
        return [self.long_flag]

    def value_name(self):
        """Human-readable type/metavar name for the plan page."""
        if self.action == 'store_true':
            return 'flag'
        if self.metavar:
            return self.metavar
        if self.type is int:
            return 'INT'
        return self.dest.upper()

    @property
    def config_key(self):
        """The long-flag spelling usable as a library config key.

        Library callers may pass either the argparse ``dest`` (e.g.
        ``pattern``) or the long flag name without dashes (e.g.
        ``grep``), mirroring the CLI flag.
        """
        return self.long_flag.lstrip('-').replace('-', '_')


class Filter(object):
    #: Filter name (also the registry key).
    name = ""
    #: Short human-readable description.
    desc = ""
    #: List of :class:`logdissect.filters.OptionSpec` contributed by this
    #: filter.
    options = []
    #: Entry fields the filter reads (``raw_text`` is always implicit).
    required_fields = ['raw_text']
    #: Static execution priority; lower numbers run first.
    priority = 100
    #: True for cross-entry state filters (e.g. range/last).
    stateful = False

    def __init__(self, args=None):
        """Initialize a filter module.

        ``args`` is accepted for backwards compatibility; the argparse
        options of registered filters are generated from
        :attr:`options` by the registry instead.
        """
        pass

    def is_active(self, args):
        """Return True if this filter is enabled by ``args``/config."""
        for spec in self.options:
            if not spec.activates:
                continue
            value = getattr(args, spec.dest, None)
            if value not in (None, False, []):
                return True
        return False

    def extract_values(self, args):
        """Return ``(primary, secondary)`` values pulled from ``args``."""
        primary = None
        secondary = {}
        for spec in self.options:
            value = getattr(args, spec.dest, None)
            if spec.activates:
                if value not in (None, False, []):
                    primary = value
            elif primary is not None and value not in (None, False):
                secondary[spec.dest] = value
        return primary, secondary

    def apply(self, data, args):
        """Run this filter against ``data`` using framework conventions."""
        values, secondary = self.extract_values(args)
        return self.filter_data(data, values=values, args=args, **secondary)

    def filter_data(self, data, values=None, args=None, **kwargs):
        """Filter log data in some way (single log)."""
        return data


# Backwards compatible alias (filters historically subclassed FilterModule).
FilterModule = Filter
