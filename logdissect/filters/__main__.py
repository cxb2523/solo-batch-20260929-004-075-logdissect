"""Entry point for ``python -m logdissect.filters`` (used by make)."""

import sys

from logdissect.filters.plan import render_text, write_html


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--html' in argv:
        index = argv.index('--html')
        path = argv[index + 1] if index + 1 < len(argv) \
                else 'build/filters.html'
        write_html(path)
        print('Wrote ' + path)
    else:
        print(render_text())
    return 0


if __name__ == '__main__':
    sys.exit(main())
