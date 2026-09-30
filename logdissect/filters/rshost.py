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
from logdissect.filters import field_filter_data
from logdissect.filters.type import FilterModule as OurModule
from logdissect.filters.type import OptionSpec

@registry.register
class FilterModule(OurModule):
    def __init__(self, args=None):
        """Initialize the reverse source host filter module"""
        self.name = "rshost"
        self.desc = "filter out a source host"
        self.required_fields = ['source_host']
        self.priority = 60
        self.options = [
            OptionSpec('--rshost', dest='rshost', action='append',
                    type=str, metavar='SHOST',
                    help='filter out a source host'),
        ]

    def filter_data(self, data, values=None, args=None):
        """Remove entries from specified source host (single log)"""
        if values is None and args is not None:
            values = getattr(args, 'rshost', None)
        if not values:
            return data
        return field_filter_data(data, values, 'source_host',
                exclude=True)
