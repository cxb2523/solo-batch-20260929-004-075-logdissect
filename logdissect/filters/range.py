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

from logdissect.filters import Filter, register, FilterOption


@register
class FilterModule(Filter):
    name = "range"
    desc = "match a time range (YYYYMMDDhhmm-YYYYMMDDhhmm)"
    required_fields = ('numeric_date_stamp', 'numeric_date_stamp_utc')
    # Cross-entry window over the merged, sorted stream; bounds are
    # computed once from the configured range.
    stateful = True
    priority = 10
    options = [
            FilterOption('--range', action='store', dest='range',
                    kind='value',
                    help='match a time range '
                    '(YYYYMMDDhhmm-YYYYMMDDhhmm)'),
            FilterOption('--utc', action='store_true', dest='utc',
                    kind='flag',
                    help='use UTC for range matching'),
            ]

    def filter_data(self, data, value=None, utc=False, args=None, **kwargs):
        """Morph log data by timestamp range (single log)"""
        if args is not None:
            value = args.range
            utc = args.utc
        if not value:
            return data

        ourlimits = value.split('-')

        newdata = {'entries': []}
        self.copy_meta(data, newdata)

        firstdate = int(ourlimits[0].ljust(14, '0'))
        lastdate = int(ourlimits[1].ljust(14, '0'))
        for entry in data['entries']:
            if utc:
                if 'numeric_date_stamp_utc' in entry:
                    if '.' in entry['numeric_date_stamp_utc']:
                        dstamp = int(
                                entry['numeric_date_stamp_utc'].split(
                                    '.')[0])
                    else:
                        dstamp = int(entry['numeric_date_stamp_utc'])
                    if firstdate <= dstamp <= lastdate:
                        newdata['entries'].append(entry)
            else:
                if 'numeric_date_stamp' in entry:
                    if '.' in entry['numeric_date_stamp']:
                        dstamp = int(
                                entry['numeric_date_stamp'].split('.')[0])
                    else:
                        dstamp = int(entry['numeric_date_stamp'])
                    if firstdate <= dstamp <= lastdate:
                        newdata['entries'].append(entry)

        return newdata
