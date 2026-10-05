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
    name = "dhost"
    desc = "match a destination host"
    required_fields = ('dest_host',)
    stateful = False
    priority = 30
    options = [
            FilterOption('--dhost', action='append', dest='dhost',
                    metavar='DHOST', kind='list',
                    help='match a destination host'),
            ]

    def filter_data(self, data, values=None, args=None, **kwargs):
        """Return entries with specified destination host (single log)"""
        if args is not None:
            values = args.dhost
        if not values:
            return data

        newdata = {'entries': []}
        self.copy_meta(data, newdata)

        for entry in data['entries']:
            if 'dest_host' in entry and entry['dest_host'] in values:
                newdata['entries'].append(entry)

        return newdata
