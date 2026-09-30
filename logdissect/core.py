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
import string
from types import SimpleNamespace
import logdissect.parsers
import logdissect.filters
import logdissect.output
from logdissect import __version__
from logdissect.filters import registry as filter_registry
from logdissect.filters.plan import render_text as render_filter_plan
from argparse import ArgumentParser
import gettext
gettext.install('logdissect')


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

    def _build_config(self, config=None, files=None, argv=None):
        """Build the args namespace from CLI argv or a library config.

        Both entry points end up in the same argparse namespace:

        * CLI -- the registered filter options are parsed from argv;
        * library -- a config dict is coerced to the same shape
          (scalars for repeatable options become one-item lists).

        The registry-built filter plan is the only place filters run,
        so identical configurations produce identical results.
        """
        if config is None and argv is None:
            argv = sys.argv[1:]
        if config is not None:
            # parse_args() overwrites pre-set namespace attributes with
            # option defaults, so parse the defaults first and layer the
            # supplied configuration on top afterwards.
            namespace = self.arg_parser.parse_args([])
            for key, value in vars(
                    self._namespace_from_config(config)).items():
                setattr(namespace, key, value)
            if files is not None:
                namespace.files = list(files)
            self.args = namespace
        else:
            self.args = self.arg_parser.parse_args(argv)
        return self.args

    def _namespace_from_config(self, config):
        """Coerce a library config mapping/namespace to argparse shape."""
        if hasattr(config, '__dict__') and not isinstance(config, dict):
            source = vars(config)
        else:
            source = dict(config)
        append_dests = set(spec.dest
                for spec in filter_registry.options()
                if spec.action == 'append')
        # Library configs may use the long-flag spelling (grep=...) in
        # addition to the argparse destination (pattern=...).
        alias_to_dest = dict((spec.config_key, spec.dest)
                for spec in filter_registry.options()
                if spec.config_key != spec.dest)
        normalized = {}
        for key, value in source.items():
            key = alias_to_dest.get(key, key)
            if key in append_dests and value is not None and \
                    not isinstance(value, (list, tuple)):
                value = [value]
            normalized[key] = value
        return SimpleNamespace(**normalized)

        
    # run_job does the actual job using the other functions.
    def run_job(self, config=None, files=None, argv=None):
        """Execute a logdissect job"""
        try:
            self.load_parsers()
            self.load_filters()
            self.load_outputs()
            self.config_args(config=config, files=files, argv=argv)
            if getattr(self.args, 'filter_plan', False):
                print(render_filter_plan(self.args))
                return 0
            if self.args.list_parsers:
                self.list_parsers()
            if self.args.verbosemode: print('Loading input files')
            self.load_inputs()
            if self.args.verbosemode: print('Running parsers')
            self.run_parse()
            if self.args.verbosemode: print('Merging data')
            self.data_set['finalized_data'] = \
                    logdissect.utils.merge_logs(
                            self.data_set['data_set'], sort=True)
            if self.args.verbosemode: print('Running filters')
            self.run_filters()
            if self.args.verbosemode: print('Running output')
            self.run_output()
        except KeyboardInterrupt:
            sys.exit(1)

    def run_parse(self):
        """Parse one or more log files"""
        # Data set already has source file names from load_inputs
        parsedset = {}
        parsedset['data_set'] = []
        for log in self.input_files:
            parsemodule = self.parse_modules[self.args.parser]
            try:
                if self.args.tzone:
                    parsemodule.tzone = self.args.tzone
            except NameError: pass
            parsedset['data_set'].append(parsemodule.parse_file(log))
        self.data_set = parsedset
        del(parsedset)

    def run_filters(self):
        """Run the registry-built execution plan over the merged data."""
        plan = filter_registry.build_plan(self.args)
        self.data_set['finalized_data'] = filter_registry.apply_plan(
                self.data_set['finalized_data'], self.args, plan=plan)

    def run_output(self):
        """Output finalized data"""
        for f in logdissect.output.__formats__:
            ouroutput = self.output_modules[f]
            ouroutput.write_output(self.data_set['finalized_data'],
                    args=self.args)
            del(ouroutput)

        # Output to terminal if silent mode is not set:
        if not self.args.silentmode:
            if self.args.verbosemode:
                print('\n==== ++++ ==== Output: ==== ++++ ====\n')
            for line in self.data_set['finalized_data']['entries']:
                print(line['raw_text'])



    def config_args(self, config=None, files=None, argv=None):
        """Set config options"""
        # Module list options:
        self.arg_parser.add_argument('--version', action='version',
                version='%(prog)s ' + str(__version__))
        self.arg_parser.add_argument('-v', '--verbose',
                action='store_true', dest = 'verbosemode',
                help=_('set verbose terminal output'))
        self.arg_parser.add_argument('-s',
                action='store_true', dest = 'silentmode',
                help=_('silence terminal output'))
        self.arg_parser.add_argument('--list-parsers',
                action='store_true', dest='list_parsers',
                help=_('return a list of available parsers'))
        self.arg_parser.add_argument('-p',
                action='store', dest='parser', default='syslog',
                help=_('select a parser (default: syslog)'))
        self.arg_parser.add_argument('-z', '--unzip',
                action='store_true', dest='unzip',
                help=_('include files compressed with gzip'))
        self.arg_parser.add_argument('-t',
                action='store', dest='tzone',
                help=_('specify timezone offset to UTC (e.g. \'+0500\')'))
        self.arg_parser.add_argument('--filter-plan',
                action='store_true', dest='filter_plan',
                help=_('print the filter pipeline (options, dependent '
                       'fields, execution order) and exit'))
        self.arg_parser.add_argument('files',
                # nargs needs to be * not + so --list-filters/etc
                # will work without file arg
                metavar='file', nargs='*',
                help=_('specify input files'))

        # Filter options are generated from the registry. Each filter
        # self-reports its flags, value type and help text; the legacy
        # long flags/metavars/help strings are preserved exactly. Any
        # short-option collision raises FilterRegistrationError here.
        filter_registry.add_arguments(self.filter_args)

        self._build_config(config=config, files=files, argv=argv)

    
    
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
                print('File '+ f + ' not found')
                return 1

    # Parsing modules:
    def list_parsers(self, *args):
        """Return a list of available parsing modules"""
        print('==== Available parsing modules: ====\n')
        for parser in sorted(self.parse_modules):
            print(self.parse_modules[parser].name.ljust(16) + \
                ': ' + self.parse_modules[parser].desc)
        sys.exit(0)
    
    def load_parsers(self):
        """Load parsing module(s)"""
        for parser in sorted(logdissect.parsers.__all__):
            self.parse_modules[parser] = \
                __import__('logdissect.parsers.' + parser, globals(), \
                locals(), [logdissect]).ParseModule()

    def load_filters(self):
        """Load filter modules from the global filter registry."""
        for name in sorted(filter_registry.names()):
            self.filter_modules[name] = filter_registry.get(name)

    def load_outputs(self):
        """Load output module(s)"""
        for output in sorted(logdissect.output.__formats__):
            self.output_modules[output] = \
                __import__('logdissect.output.' + output, globals(), \
                locals(), [logdissect]).OutputModule(args=self.output_args)


                
def main():
    dissect = LogDissectCore()
    dissect.run_job()
                
if __name__ == "__main__":
    dissect = LogDissectCore()
    dissect.run_job()
