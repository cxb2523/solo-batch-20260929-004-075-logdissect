"""Render the registered filter pipeline as text or HTML.

Used by the ``--filter-plan`` CLI flag and the
``make filter-plan`` / ``python -m logdissect.filters`` command, which
writes ``build/filters.html``.
"""

import html
import os

from logdissect.filters import registry


def render_text(args=None):
    """Plain-text pipeline listing (order, options, dependent fields)."""
    return registry.render_plan_text(args)


def render_html(args=None):
    """HTML page listing each filter's options, fields and execution order."""
    rows = []
    for index, ourfilter in enumerate(registry.build_full_plan(), 1):
        option_items = []
        for spec in ourfilter.options:
            label = spec.long_flag
            if spec.short_flag:
                label = spec.short_flag + ' / ' + label
            if spec.action != 'store_true':
                label += ' ' + spec.value_name()
            role = 'modifier' if not spec.activates else \
                    ('repeatable' if spec.action == 'append'
                             else 'value')
            option_items.append(
                    '<li><code>%s</code> <em>(%s)</em> &mdash; %s</li>'
                    % (html.escape(label), html.escape(role),
                        html.escape(spec.help)))
        if not option_items:
            option_items.append('<li><em>(no options)</em></li>')
        fields = ', '.join(ourfilter.required_fields)
        kind = 'stateful (grouped for streaming input)' \
                if ourfilter.stateful else 'stateless'
        rows.append(
                '<tr>'
                '<td class="order">{index}</td>'
                '<td><code>{name}</code><br><small>{desc}</small></td>'
                '<td>{priority}</td>'
                '<td>{kind}</td>'
                '<td><code>{fields}</code></td>'
                '<td><ul class="options">{options}</ul></td>'
                '</tr>'.format(
                    index=index,
                    name=html.escape(ourfilter.name),
                    desc=html.escape(ourfilter.desc),
                    priority=ourfilter.priority,
                    kind=html.escape(kind),
                    fields=html.escape(fields),
                    options=''.join(option_items)))
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>logdissect filter pipeline</title>
<style>
body {{ font-family: sans-serif; margin: 2em; color: #222; }}
h1 {{ margin-bottom: 0.2em; }}
p.note {{ color: #555; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #bbb; padding: 0.5em 0.7em;
    vertical-align: top; text-align: left; }}
th {{ background: #f0f0f0; }}
td.order {{ text-align: right; font-weight: bold; }}
ul.options {{ margin: 0; padding-left: 1.2em; }}
code {{ background: #f5f5f5; padding: 0 0.25em; }}
</style>
</head>
<body>
<h1>logdissect filter pipeline</h1>
<p class="note">Filters execute in static-priority order (lowest first);
stateful filters (<code>range</code>, <code>last</code>) run on each
completed group under streaming input. Reverse filters exclude entries
and run last.</p>
<table>
<thead>
<tr>
<th>#</th><th>Filter</th><th>Priority</th><th>Kind</th>
<th>Dependent fields</th><th>CLI options</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
""".format(rows='\n'.join(rows))


def write_html(path='build/filters.html'):
    """Write the HTML plan to ``path`` (creating parent directories)."""
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, 'w') as output:
        output.write(render_html())
    return path
