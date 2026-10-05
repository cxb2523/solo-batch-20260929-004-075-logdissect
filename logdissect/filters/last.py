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

from time import strftime
from datetime import datetime, timedelta
from logdissect.filters import Filter, register, FilterOption


@register
class FilterModule(Filter):
    name = "last"
    desc = "match a preceeding time period (e.g. 5m/3h/2d/etc)"
    required_fields = ('numeric_date_stamp_utc',)
    # Cross-entry window: its start is computed once from "now" and
    # applied to the whole merged, sorted stream.  Runs first so the
    # window is evaluated once, globally (CLI and library alike).
    stateful = True
    priority = 10
    options = [
            FilterOption('--last', action='store', dest='last',
                    kind='value',
                    help='match a preceeding time period '
                    '(e.g. 5m/3h/2d/etc)'),
            ]

    def filter_data(self, data, value=None, args=None, **kwargs):
        """Morph log data by preceeding time period (single log)"""
        if args is not None:
            value = args.last
        if not value:
            return data

        # Set the units and number from the option:
        lastunit = value[-1]
        lastnum = value[:-1]

        # Set the start time:
        if lastunit == 's':
            starttime = datetime.utcnow() - \
                    timedelta(seconds=int(lastnum))
        if lastunit == 'm':
            starttime = datetime.utcnow() - \
                    timedelta(minutes=int(lastnum))
        if lastunit == 'h':
            starttime = datetime.utcnow() - \
                    timedelta(hours=int(lastnum))
        if lastunit == 'd':
            starttime = datetime.utcnow() - \
                    timedelta(days=int(lastnum))
        ourstart = int(starttime.strftime('%Y%m%d%H%M%S'))

        newdata = {'entries': []}
        self.copy_meta(data, newdata)

        for entry in data['entries']:
            if 'numeric_date_stamp_utc' in entry:
                if '.' in entry['numeric_date_stamp_utc']:
                    dstamp = int(
                            entry['numeric_date_stamp_utc'].split('.')[0])
                else:
                    dstamp = int(entry['numeric_date_stamp_utc'])
                if dstamp >= ourstart:
                    newdata['entries'].append(entry)

        return newdata
