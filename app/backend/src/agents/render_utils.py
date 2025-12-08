from markupsafe import escape


def render_html_table(rows, columns=None):
    if not rows:
        return "<p>No data available.</p>"

    columns = columns or list(rows[0].keys())
    html = ["<table class='analytics-table'>"]

    html.append("<thead><tr>")
    for col in columns:
        html.append(f"<th>{escape(col)}</th>")
    html.append("</tr></thead>")

    html.append("<tbody>")
    for row in rows:
        html.append("<tr>")
        for col in columns:
            val = row.get(col, "")
            html.append(f"<td>{escape(val)}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")

    return "".join(html)
