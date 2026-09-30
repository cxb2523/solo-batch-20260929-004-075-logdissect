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

from logdissect.filters import registry
from logdissect.filters.type import FilterModule as OurModule
from logdissect.filters.type import OptionSpec


def _copy_metadata(data, newdata):
    for key in ('parser', 'source_path', 'source_file',
            'source_file_mtime', 'source_file_year'):
        if key in data:
            newdata[key] = data[key]


@registry.register
class FilterModule(OurModule):
    def __init__(self, args=None):
        """Initialize the range filter module"""
        self.name = "range"
        self.desc = "match a time range (YYYYMMDDhhmm-YYYYMMDDhhmm)"
        self.required_fields = ['numeric_date_stamp',
                'numeric_date_stamp_utc']
        self.priority = 20
        self.stateful = True
        self.options = [
            OptionSpec('--range', dest='range', action='store', type=str,
                    short_flag='-R',
                    help='match a time range '
                         '(YYYYMMDDhhmm-YYYYMMDDhhmm)'),
            OptionSpec('--utc', dest='utc', action='store_true',
                    default=False, help='use UTC for range matching',
                    activates=False),
        ]

    def filter_data(self, data, values=None, value=None, utc=False,
            args=None, **kwargs):
        """Morph log data by timestamp range (single log)"""
        if values is None:
            values = value
        if values is None and args is not None:
            values = getattr(args, 'range', None)
            utc = getattr(args, 'utc', utc)
        if not values:
            return data
        value = values
        ourlimits = value.split('-')

        newdata = {}
        _copy_metadata(data, newdata)
        newdata['entries'] = []

        firstdate = int(ourlimits[0].ljust(14, '0'))
        lastdate = int(ourlimits[1].ljust(14, '0'))
        stampkey = 'numeric_date_stamp_utc' if utc \
                else 'numeric_date_stamp'
        for entry in data['entries']:
            if stampkey in entry:
                if '.' in entry[stampkey]:
                    dstamp = int(entry[stampkey].split('.')[0])
                else:
                    dstamp = int(entry[stampkey])
                if firstdate <= dstamp <= lastdate:
                    newdata['entries'].append(entry)

        return newdata
