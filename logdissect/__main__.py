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

"""``python -m logdissect`` entry point.

Subcommands:
  filter-plan   write the HTML pipeline page (build/filters.html)

Without a subcommand the normal CLI job runs.
"""

import sys
from logdissect.core import main as run_cli
from logdissect.core import write_filter_plan_page


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'filter-plan':
        out = argv[1] if len(argv) > 1 else 'build/filters.html'
        path = write_filter_plan_page(out)
        print('Wrote filter pipeline plan to {}'.format(path))
        return 0
    run_cli()
    return 0


if __name__ == '__main__':
    sys.exit(main())
