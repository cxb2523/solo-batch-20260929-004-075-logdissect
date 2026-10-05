#!/usr/bin/env python

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

import os
import sys
import logdissect.parsers
import logdissect.filters
import logdissect.output
from logdissect import __version__
from logdissect.filters import registry as filter_registry
from logdissect.filters import add_filter_arguments, build_plan, \
        run_pipeline, FilterOptionError
from argparse import ArgumentParser
import gettext
gettext.install('logdissect')


def render_filter_plan_text(config=None):
    """Render the registered filter pipeline as plain text."""
    lines = ['==== Filter pipeline plan ====', '']
    for step, item in enumerate(build_plan(config), start=1):
        status = 'ACTIVE' if item['active'] else 'idle'
        state = 'stateful' if item['stateful'] else 'per-entry'
        lines.append('{:>2}. [{}] {} (priority {}, {})'.format(
            step, status, item['name'], item['priority'], state))
        lines.append('      {}'.format(item['desc']))
        if item['active']:
            lines.append('      value: {}'.format(item['active_value']))
        option_strs = []
        for option in item['options']:
            flags = '/'.join(option.flags)
            option_strs.append('{} ({}, -> {})'.format(
                flags, option.kind, option.dest))
        lines.append('      options: {}'.format(
            '; '.join(option_strs) if option_strs else '(none)'))
        lines.append('      depends on fields: {}'.format(
            ', '.join(item['required_fields'])
            if item['required_fields'] else '(none)'))
    return '\n'.join(lines)


def render_filter_plan_html(config=None):
    """Render the registered filter pipeline as an HTML page."""
    import html
    rows = []
    for step, item in enumerate(build_plan(config), start=1):
        options = []
        for option in item['options']:
            options.append('<code>{}</code> <em>{}</em> &rarr; '
                    '<code>{}</code>'.format(
                        html.escape('/'.join(option.flags)),
                        html.escape(option.kind),
                        html.escape(option.dest)))
        fields = ', '.join(
                '<code>{}</code>'.format(html.escape(field))
                for field in item['required_fields']) or '(none)'
        classes = 'active' if item['active'] else 'idle'
        active_value = '<code>{}</code>'.format(
                html.escape(str(item['active_value']))) \
                if item['active'] else ''
        rows.append(
                '<tr class="{}">'.format(classes) +
                '<td class="step">{}</td>'.format(step) +
                '<td class="name">{}</td>'.format(
                    html.escape(item['name'])) +
                '<td>{}</td>'.format(html.escape(item['desc'])) +
                '<td>{}</td>'.format(item['priority']) +
                '<td>{}</td>'.format(
                    'stateful' if item['stateful'] else 'per-entry') +
                '<td>{}</td>'.format(' '.join(options) or '(none)') +
                '<td>{}</td>'.format(fields) +
                '<td>{}</td>'.format(
                    'active' if item['active'] else 'idle') +
                '<td>{}</td>'.format(active_value) +
                '</tr>')
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>logdissect filter pipeline</title>
<style>
body {{ font-family: sans-serif; margin: 2em; color: #222; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #bbb; padding: 6px 8px;
  vertical-align: top; text-align: left; }}
th {{ background: #eee; }}
tr.active {{ background: #e8f5e9; }}
td.step {{ text-align: right; width: 2.5em; }}
td.name {{ font-weight: bold; }}
code {{ background: #f4f4f4; padding: 1px 3px; }}
</style>
</head>
<body>
<h1>logdissect filter pipeline</h1>
<p>Filters execute top to bottom in static priority order. Reverse
filters are standalone exclusion predicates on the listed dependency
fields, not topological dependents of their positive counterparts.
Stateful filters window the whole merged, sorted stream.</p>
<table>
<thead><tr><th>#</th><th>Filter</th><th>Description</th><th>Priority</th>
<th>Scope</th><th>CLI options (kind &rarr; dest)</th>
<th>Dependency fields</th><th>State</th><th>Configured value</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
""".format(rows='\n'.join(rows))


def write_filter_plan_page(path='build/filters.html', config=None):
    """Write the HTML filter plan to *path* (used by ``make filter-plan``)."""
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, 'w') as plan_file:
        plan_file.write(render_filter_plan_html(config))
    return path


class LogDissectCore:

    def __init__(self):
        """Initialize logdissect job"""
        self.input_files = []
        self.parse_modules = {}
        self.filter_modules = {}
        self.output_modules = {}
        self.data_set = {}
        self.args = None
        self.arg_parser = ArgumentParser()
        self.parse_args = \
                self.arg_parser.add_argument_group('parse options')
        self.filter_args = \
                self.arg_parser.add_argument_group('filter options')
        self.output_args = \
                self.arg_parser.add_argument_group('output options')

    # run_job does the actual job using the other functions.
    def run_job(self):
        """Execute a logdissect job"""
        try:
            self.load_parsers()
            self.load_filters()
            self.load_outputs()
            self.config_args()
            if self.args.list_parsers:
                self.list_parsers()
            if self.args.filter_plan:
                print(render_filter_plan_text(self.args))
                sys.exit(0)
            if self.args.verbosemode:
                print('Loading input files')
            self.load_inputs()
            if self.args.verbosemode:
                print('Running parsers')
            self.run_parse()
            if self.args.verbosemode:
                print('Merging data')
            self.data_set['finalized_data'] = \
                    logdissect.utils.merge_logs(
                            self.data_set['data_set'], sort=True)
            if self.args.verbosemode:
                print('Running filters')
            self.run_filters()
            if self.args.verbosemode:
                print('Running output')
            self.run_output()
        except FilterOptionError as err:
            sys.stderr.write(
                    'logdissect: filter option error: {}\n'.format(err))
            sys.exit(2)
        except KeyboardInterrupt:
            sys.exit(1)

    def run_parse(self):
        """Parse one or more log files"""
        parsedset = {}
        parsedset['data_set'] = []
        for log in self.input_files:
            parsemodule = self.parse_modules[self.args.parser]
            try:
                if self.args.tzone:
                    parsemodule.tzone = self.args.tzone
            except NameError:
                pass
            parsedset['data_set'].append(parsemodule.parse_file(log))
        self.data_set = parsedset

    def run_filters(self):
        """Run active filters in registry-defined static order."""
        self.data_set['finalized_data'] = run_pipeline(
                self.data_set['finalized_data'], config=self.args,
                instances=self.filter_modules)

    def run_output(self):
        """Output finalized data"""
        for f in logdissect.output.__formats__:
            ouroutput = self.output_modules[f]
            ouroutput.write_output(self.data_set['finalized_data'],
                    args=self.args)

        # Output to terminal if silent mode is not set:
        if not self.args.silentmode:
            if self.args.verbosemode:
                print('\n==== ++++ ==== Output: ==== ++++ ====\n')
            for line in self.data_set['finalized_data']['entries']:
                print(line['raw_text'])

    def config_args(self):
        """Set config options"""
        self.arg_parser.add_argument('--version', action='version',
                version='%(prog)s ' + str(__version__))
        self.arg_parser.add_argument('--verbose',
                action='store_true', dest='verbosemode',
                help=_('set verbose terminal output'))
        self.arg_parser.add_argument('-s',
                action='store_true', dest='silentmode',
                help=_('silence terminal output'))
        self.arg_parser.add_argument('--list-parsers',
                action='store_true', dest='list_parsers',
                help=_('return a list of available parsers'))
        self.arg_parser.add_argument('--filter-plan',
                action='store_true', dest='filter_plan',
                help=_('print the filter pipeline plan and exit'))
        self.arg_parser.add_argument('-p',
                action='store', dest='parser', default='syslog',
                help=_('select a parser (default: syslog)'))
        self.arg_parser.add_argument('-z', '--unzip',
                action='store_true', dest='unzip',
                help=_('include files compressed with gzip'))
        self.arg_parser.add_argument('-t',
                action='store', dest='tzone',
                help=_("specify timezone offset to UTC (e.g. '+0500')"))
        self.arg_parser.add_argument('files',
                metavar='file', nargs='*',
                help=_('specify input files'))

        # The group re-adds reproduce the historical argparse action
        # ordering (so the usage line and help layout are unchanged).
        # Filter options were already generated into the group during
        # load_filters(); the re-adds only reposition the groups, just
        # like the old constructor based registration did.
        self.arg_parser.add_argument_group(self.filter_args)
        self.arg_parser.add_argument_group(self.output_args)
        self.args = self.arg_parser.parse_args()

    # Load input files:
    def load_inputs(self):
        """Load the specified inputs"""
        for f in self.args.files:
            if os.path.isfile(f):
                fparts = str(f).split('.')
                if fparts[-1] == 'gz':
                    if self.args.unzip:
                        fullpath = os.path.abspath(str(f))
                        self.input_files.append(fullpath)
                    else:
                        return 0
                elif fparts[-1] == 'bz2' or fparts[-1] == 'zip':
                    return 0
                else:
                    fullpath = os.path.abspath(str(f))
                    self.input_files.append(fullpath)
            else:
                print('File ' + f + ' not found')
                return 1

    # Parsing modules:
    def list_parsers(self, *args):
        """Return a list of available parsing modules"""
        print('==== Available parsing modules: ====\n')
        for parser in sorted(self.parse_modules):
            print(self.parse_modules[parser].name.ljust(16) +
                ': ' + self.parse_modules[parser].desc)
        sys.exit(0)

    def load_parsers(self):
        """Load parsing module(s)"""
        for parser in sorted(logdissect.parsers.__all__):
            self.parse_modules[parser] = \
                __import__('logdissect.parsers.' + parser, globals(),
                locals(), [logdissect]).ParseModule()

    def load_filters(self):
        """Load filter modules from the registry.

        Side effect: their declared CLI options are generated into the
        filter argument group here (not in config_args) to preserve the
        historical argparse action ordering.  A short/long option
        collision aborts startup explicitly.
        """
        add_filter_arguments(self.filter_args)
        for f in logdissect.filters.__filters__:
            self.filter_modules[f] = filter_registry[f]()

    def load_outputs(self):
        """Load output module(s)"""
        for output in sorted(logdissect.output.__formats__):
            self.output_modules[output] = \
                __import__('logdissect.output.' + output, globals(),
                locals(), [logdissect]).OutputModule(args=self.output_args)


def run_library_job(files, config, parser_name='syslog', tzone=None):
    """Library entry point mirroring the CLI path.

    Parses *files*, merges them sorted and then runs the registry
    defined filter pipeline with *config* (a dict of the same option
    names the CLI uses, e.g. ``{'pattern': ['software']}`` or
    ``{'range': '20180202020202-20180227213200'}``).  Returns the
    filtered merged log dict.  Stateful filters operate on one merged,
    sorted group, so a given config yields the same result here as on
    the command line.
    """
    parser = \
        __import__('logdissect.parsers.' + parser_name, globals(),
        locals(), [logdissect]).ParseModule()
    if tzone:
        parser.tzone = tzone
    dataset = []
    for path in files:
        dataset.append(parser.parse_file(os.path.abspath(str(path))))
    merged = logdissect.utils.merge_logs(dataset, sort=True)
    return run_pipeline(merged, config=config)


def main():
    dissect = LogDissectCore()
    dissect.run_job()


if __name__ == "__main__":
    dissect = LogDissectCore()
    dissect.run_job()
