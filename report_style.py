"""Shared look for the WhatsApp PDF reports, plus a Markdown copy of the same content.

The copy in Chat Stats is the original. Other local projects may carry a
copy; ``Tools/sync_shared.sh`` in the parent folder updates them.
Uses only the standard library.
"""
from __future__ import annotations

import html

ACCENT = "#0f766e"

CSS = """
@page {
    size: A4;
    margin: 17mm 15mm 18mm;
    @bottom-left { content: string(report-title); font-family: "Helvetica Neue", Arial, "DejaVu Sans", sans-serif;
                   font-size: 7.5pt; color: #64748b; }
    @bottom-right { content: counter(page) " / " counter(pages); font-family: "Helvetica Neue", Arial, "DejaVu Sans", sans-serif;
                    font-size: 7.5pt; color: #64748b; }
}
body { font-family: "Helvetica Neue", Arial, "DejaVu Sans", sans-serif; font-size: 9pt;
       line-height: 1.45; color: #17253b; }
.eyebrow { color: #0f766e; font-size: 8.5pt; font-weight: bold; letter-spacing: 1.5px; }
h1 { string-set: report-title content(); font-size: 25pt; line-height: 1.15; margin: 5px 0 6px; color: #10253f; }
.meta { color: #64748b; font-size: 8.5pt; margin: 0 0 10px; }
h2 { font-size: 14pt; color: #10253f; margin: 22px 0 8px; padding-bottom: 4px;
     border-bottom: 2px solid #0f766e; break-after: avoid; }
h3 { font-size: 10.5pt; color: #334155; margin: 12px 0 5px; break-after: avoid; }
p { margin: 6px 0; }
.note { color: #64748b; font-size: 8pt; break-after: avoid; }
.kpis { width: 100%; border-collapse: separate; border-spacing: 5px 0; margin: 4px -5px 6px; table-layout: fixed; }
.kpis td { background: #eff3f8; padding: 10px 10px; border: 0; vertical-align: top; }
.kpis .value { display: block; font-size: 17pt; font-weight: bold; color: #0f766e; line-height: 1.2; }
.kpis .label { display: block; font-size: 7.5pt; color: #475569; margin-top: 2px; }
table.data { border-collapse: collapse; width: 100%; margin: 4px 0 12px; font-size: 8.5pt; }
table.data th, table.data td { border-bottom: 1px solid #e2e8f0; padding: 3.5px 7px; text-align: left; }
table.data th { background: #e6f2f1; color: #10253f; font-weight: bold; }
table.data tr { break-inside: avoid; }
table.data tbody tr:nth-child(even) td { background: #f8fafc; }
table.data .num { text-align: right; white-space: nowrap; }
table.data.emoji td:first-child { font-size: 13pt; line-height: 1.1; }
table.data tr.total td { font-weight: bold; border-top: 1.5px solid #94a3b8; background: #fff; }
.grid { display: grid; gap: 0 14px; }
.grid.cols-2 { grid-template-columns: 1fr 1fr; }
.grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
.block { break-inside: avoid; }
.keep { break-inside: avoid; }
.termlist { columns: 3; column-gap: 16px; margin: 2px 0 12px; font-size: 8.5pt; }
.termlist.cols-2 { columns: 2; }
.termlist .item { display: flex; justify-content: space-between; padding: 3px 6px;
                  border-bottom: 1px solid #e2e8f0; break-inside: avoid; }
.termlist .item:nth-child(even) { background: #f8fafc; }
.termlist .count { padding-left: 8px; white-space: nowrap; }
.person { break-inside: avoid; margin: 14px 0 6px; }
.person .band { display: flex; justify-content: space-between; align-items: baseline;
                background: #e6f2f1; border-left: 4px solid #0f766e; padding: 6px 10px; margin-bottom: 6px; }
.person .name { font-weight: bold; font-size: 11pt; color: #10253f; }
.person .details { font-size: 8pt; color: #475569; }
.more { color: #64748b; font-size: 7.5pt; margin: -8px 0 10px; }
.caption { break-after: avoid;  color: #64748b; font-size: 7.5pt; margin: 0 0 2px; }
.chart { display: block; width: 100%; margin: 2px 0 10px; }
.bar { display: inline-block; height: 7px; background: #0f766e; border-radius: 1px; vertical-align: middle; }
"""


def escape(value) -> str:
    return html.escape(str(value), quote=False)


def number(value) -> str:
    """Turkish grouping: 1.234 and 12,50."""
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{value:,}".replace(",", ".")


def decimal(value, digits=1) -> str:
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def percent(value, digits=1) -> str:
    return "%" + decimal(value, digits)


def date_time(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


def md_text(value) -> str:
    """Escape a name or word for a Markdown table cell or heading."""
    text = escape(value).replace("\\", "\\\\")
    for char in "|*_`[]#":
        text = text.replace(char, "\\" + char)
    return text


class Report:
    """Collect a report once and render it as a styled HTML page and as Markdown."""

    def __init__(self, title, meta, kpis):
        self.title = title
        self._html = [
            '<div class="eyebrow">WHATSAPP SOHBET ANALİZİ</div>',
            f"<h1>{escape(title)}</h1>",
            f'<p class="meta">{" · ".join(escape(part) for part in meta)}</p>',
            '<table class="kpis"><tr>'
            + "".join(
                f'<td><span class="value">{escape(value)}</span><span class="label">{escape(label)}</span></td>'
                for label, value in kpis
            )
            + "</tr></table>",
        ]
        self._md = [f"# {title}\n\n", "  \n".join(escape(part) for part in meta) + "\n\n"]
        self._md.append("".join(f"**{label}:** {value}  \n" for label, value in kpis) + "\n")

    def section(self, title):
        self._html.append(f"<h2>{escape(title)}</h2>")
        self._md.append(f"\n## {title}\n\n")

    def subsection(self, title):
        self._html.append(f"<h3>{escape(title)}</h3>")
        self._md.append(f"\n### {md_text(title)}\n\n")

    def chart_block(self, title, data_uri):
        """A titled chart that stays on one page; its Markdown copy is a note."""
        self._html.append(
            f'<div class="block"><h3>{escape(title)}</h3>'
            f'<img class="chart" src="{data_uri}" alt="{escape(title)}" /></div>'
        )
        self._md.append(f"\n### {title}\n\n*Grafik PDF raporunda yer alır.*\n")

    def paragraph(self, text, css_class=None):
        attribute = f' class="{css_class}"' if css_class else ""
        self._html.append(f"<p{attribute}>{escape(text)}</p>")
        self._md.append(f"{md_text(text)}\n\n")

    def table(self, headers, rows, numeric=(), title=None, total=None, bar_column=None, bar_values=None,
              css_class=""):
        """Add a table; ``numeric`` holds the right-aligned column indexes.

        ``total`` is an optional bold last row. With ``bar_column`` and one
        number per row in ``bar_values``, that column also gets a small bar so
        the rows can be compared at a glance (PDF only).
        """
        numeric = set(numeric)
        top = max(bar_values) if bar_values else 0

        def cell(tag, index, value, bar=None):
            css = ' class="num"' if index in numeric else ""
            content = escape(value)
            if bar is not None and top:
                width = max(1, round(44 * bar / top))
                content = f'<span class="bar" style="width:{width}px"></span> {content}'
            return f"<{tag}{css}>{content}</{tag}>"

        body = []
        for row_index, row in enumerate(rows):
            bar = bar_values[row_index] if bar_values else None
            body.append("<tr>" + "".join(
                cell("td", i, v, bar if i == bar_column else None) for i, v in enumerate(row)
            ) + "</tr>")
        if total:
            body.append('<tr class="total">' + "".join(cell("td", i, v) for i, v in enumerate(total)) + "</tr>")
        head = "".join(cell("th", i, h) for i, h in enumerate(headers))
        heading = f"<h3>{escape(title)}</h3>" if title else ""
        # Short tables stay on one page; long ones may break across pages.
        keep = ' class="keep"' if len(rows) <= 15 else ""
        self._html.append(
            f'<div{keep}>{heading}<table class="data {css_class}"><thead><tr>{head}</tr></thead>'
            f"<tbody>{''.join(body)}</tbody></table></div>"
        )

        if title:
            self._md.append(f"\n**{md_text(title)}**\n\n")
        self._md.append("| " + " | ".join(md_text(h) for h in headers) + " |\n")
        self._md.append("|" + "|".join("---:" if i in numeric else "---" for i in range(len(headers))) + "|\n")
        for row in [*rows, *([total] if total else [])]:
            self._md.append("| " + " | ".join(md_text(v) for v in row) + " |\n")
        self._md.append("\n")

    def term_list(self, headers, rows, title=None, columns=3, more=0):
        """A long two-column list (word and count) that flows in newspaper-style
        columns. Unlike tables side by side, it splits cleanly across pages.
        ``more`` is how many further entries were left out of ``rows``.
        """
        heading = f"<h3>{escape(title)}</h3>" if title else ""
        items = "".join(
            f'<div class="item"><span>{escape(term)}</span><span class="count">{escape(count)}</span></div>'
            for term, count in rows
        )
        self._html.append(
            f'{heading}<p class="caption">{escape(headers[0])} · {escape(headers[1])}</p>'
            f'<div class="termlist cols-{columns}">{items}</div>'
        )
        if more:
            self._html.append(f'<p class="more">… ve {number(more)} ifade daha</p>')
        if title:
            self._md.append(f"\n**{md_text(title)}**\n\n")
        self._md.append(f"| {md_text(headers[0])} | {md_text(headers[1])} |\n|---|---:|\n")
        self._md.append("".join(f"| {md_text(term)} | {md_text(count)} |\n" for term, count in rows))
        self._md.append(f"\n*… ve {number(more)} ifade daha*\n\n" if more else "\n")

    def person(self, name, details):
        """A highlighted band for one person; what follows inside the ``with``
        block stays on the same page as the band.
        """
        report = self

        class _Person:
            def __enter__(self):
                report._html.append(
                    f'<div class="person"><div class="band"><span class="name">{escape(name)}</span>'
                    f'<span class="details">{escape(" · ".join(details))}</span></div>'
                )
                report._md.append(f"\n### {md_text(name)}\n\n{' · '.join(details)}\n\n")

            def __exit__(self, *exc):
                report._html.append("</div>")

        return _Person()

    def grid(self, columns, title=None):
        """Lay the tables added inside ``with report.grid(n):`` side by side in the PDF.

        With a ``title``, the heading and the tables stay together on one page.
        """
        report = self

        class _Grid:
            def __enter__(self):
                if title:
                    report._html.append(f'<div class="block"><h3>{escape(title)}</h3>')
                    report._md.append(f"\n### {md_text(title)}\n\n")
                report._html.append(f'<div class="grid cols-{columns}">')

            def __exit__(self, *exc):
                report._html.append("</div></div>" if title else "</div>")

        return _Grid()

    def html(self) -> str:
        return (
            '<!DOCTYPE html>\n<html lang="tr"><head><meta charset="utf-8">'
            f"<title>{escape(self.title)}</title><style>{CSS}</style></head>\n<body>\n"
            + "\n".join(self._html)
            + "\n</body></html>\n"
        )

    def markdown(self) -> str:
        return "".join(self._md).rstrip() + "\n"
