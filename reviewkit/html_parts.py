"""Small escaped HTML primitives shared by the fixed renderer."""

import html


def e(value):
    return html.escape(str(value))


def pre(value):
    return "<pre>" + e(value) + "</pre>"


def p(value):
    return "<p>" + e(value) + "</p>"


def fold(title, body):
    return (
        "<details><summary>"
        + e(title)
        + '</summary><div class="inside">'
        + body
        + "</div></details>"
    )


def table(headers, rows):
    head = "".join("<th>" + e(x) + "</th>" for x in headers)
    body = "".join(
        "<tr>" + "".join("<td>" + str(v) + "</td>" for v in row) + "</tr>" for row in rows
    )
    return (
        '<div class="table-scroll"><table><thead><tr>'
        + head
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
    )
