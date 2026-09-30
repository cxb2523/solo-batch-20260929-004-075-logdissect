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

import re
from logdissect.filters import registry
from logdissect.filters.type import FilterModule as OurModule
from logdissect.filters.type import OptionSpec

@registry.register
class FilterModule(OurModule):
    def __init__(self, args=None):
        """Initialize the rgrep filter module"""
        self.name = "rgrep"
        self.desc = "filter out a pattern"
        self.required_fields = ['raw_text']
        self.priority = 60
        self.options = [
            OptionSpec('--rgrep', dest='rpattern', action='append',
                    type=str, short_flag='-G', metavar='PATTERN',
                    help='filter out a pattern'),
        ]

    def filter_data(self, data, values=None, args=None, **kwargs):
        """Remove entries containing any specified pattern (single log)

        Entries matching *any* pattern are dropped. The legacy version
        compiled every pattern from ``args.rpattern`` and crashed on
        library calls without ``args``; both paths now share this code.
        """
        if values is None and args is not None:
            values = getattr(args, 'rpattern', None)
        if not values:
            return data
        newdata = {}
        for key in ('parser', 'source_path', 'source_file',
                'source_file_mtime', 'source_file_year'):
            if key in data:
                newdata[key] = data[key]
        newdata['entries'] = []

        repatterns = {}
        for rpat in values:
            repatterns[rpat] = re.compile(r".*({}).*".format(rpat))

        for entry in data['entries']:
            match = False
            for rpat in values:
                if re.match(repatterns[rpat], entry['raw_text']):
                    match = True
                    break

            if not match:
                newdata['entries'].append(entry)

        return newdata
