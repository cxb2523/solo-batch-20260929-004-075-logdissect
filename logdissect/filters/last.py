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

from datetime import datetime, timedelta

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
        """Initialize the 'last' filter module"""
        self.name = "last"
        self.desc = "match a preceeding time period (e.g. 5m/3h/2d/etc)"
        self.required_fields = ['numeric_date_stamp_utc']
        self.priority = 10
        self.stateful = True
        self.options = [
            OptionSpec('--last', dest='last', action='store', type=str,
                    short_flag='-L',
                    help='match a preceeding time period '
                         '(e.g. 5m/3h/2d/etc)'),
        ]

    def filter_data(self, data, values=None, args=None, **kwargs):
        """Morph log data by preceeding time period (single log)"""
        value = values
        if value is None and args is not None:
            value = getattr(args, 'last', None)
        if not value:
            return data

        # Set the units and number from the option:
        lastunit = value[-1]
        lastnum = value[:-1]

        # Set the start time:
        if lastunit == 's':
            starttime = datetime.utcnow() - \
                    timedelta(seconds=int(lastnum))
        elif lastunit == 'm':
            starttime = datetime.utcnow() - \
                    timedelta(minutes=int(lastnum))
        elif lastunit == 'h':
            starttime = datetime.utcnow() - \
                    timedelta(hours=int(lastnum))
        elif lastunit == 'd':
            starttime = datetime.utcnow() - \
                    timedelta(days=int(lastnum))
        else:
            return data
        ourstart = int(starttime.strftime('%Y%m%d%H%M%S'))

        # Pull out the specified time period:
        newdata = {}
        _copy_metadata(data, newdata)
        newdata['entries'] = []

        for entry in data['entries']:
            if 'numeric_date_stamp_utc' in entry:
                dstamp = int(
                        entry['numeric_date_stamp_utc'].split('.')[0])
                if dstamp >= ourstart:
                    newdata['entries'].append(entry)

        return newdata
