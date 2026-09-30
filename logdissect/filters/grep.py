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
        """Initialize the grep filter module"""
        self.name = "grep"
        self.desc = "match a pattern"
        self.required_fields = ['raw_text']
        self.priority = 30
        self.options = [
            OptionSpec('--grep', dest='pattern', action='append',
                    type=str, short_flag='-g', metavar='PATTERN',
                    help='match a pattern'),
        ]

    def filter_data(self, data, values=None, args=None, **kwargs):
        """Return entries containing specified patterns (single log)

        Multiple patterns combine with OR semantics (an entry is kept if
        it matches any of them), matching the legacy CLI behavior.
        """
        if values is None and args is not None:
            values = getattr(args, 'pattern', None)
        if not values:
            return data
        newdata = {}
        for key in ('parser', 'source_path', 'source_file',
                'source_file_mtime', 'source_file_year'):
            if key in data:
                newdata[key] = data[key]
        newdata['entries'] = []

        repatterns = {}
        for pat in values:
            repatterns[pat] = re.compile(r".*({}).*".format(pat))

        for entry in data['entries']:
            for repat in repatterns:
                if re.match(repatterns[repat], entry['raw_text']):
                    newdata['entries'].append(entry)
                    break

        return newdata
