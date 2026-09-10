import json
import re
import sys


def find_matching(text, start, opening, closing):
    depth = 0

    for i in range(start, len(text)):
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1

            if depth == 0:
                return i

    return -1


def get_reports_sections(text):
    sections = []

    pattern = re.compile(
        r'\breports\s*\{',
        re.IGNORECASE
    )

    for match in pattern.finditer(text):

        open_pos = match.end() - 1

        close_pos = find_matching(
            text,
            open_pos,
            "{",
            "}"
        )

        if close_pos == -1:
            continue

        sections.append(
            text[
                open_pos + 1:
                close_pos
            ]
        )

    return sections


def get_report_forms(reports_section):
    result = {}

    pattern = re.compile(
        r'\b(?:default\s+list|list)\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    for match in pattern.finditer(reports_section):

        report_name = match.group(1)

        open_pos = match.end() - 1

        close_pos = find_matching(
            reports_section,
            open_pos,
            "{",
            "}"
        )

        if close_pos == -1:
            continue

        body = reports_section[
            open_pos + 1:
            close_pos
        ]

        form_match = re.search(
            r'\bshow\s+all\s+rows\s+from\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)',
            body,
            re.IGNORECASE
        )

        if form_match:
            result[report_name] = form_match.group(1)

    return result


def extract_fields(fields_body):
    fields = []

    for raw_line in fields_body.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s+as\s+'
            r'"(?:[^"\\]|\\.)*"'
            r')?\s*$',
            line,
            re.IGNORECASE
        )

        if match:
            fields.append(
                match.group(1)
            )

    return fields


def get_quickview_fields(report_body):

    quickview_match = re.search(
        r'\bquickview\s*\(',
        report_body,
        re.IGNORECASE
    )

    if not quickview_match:
        return []

    quickview_open = (
        quickview_match.end() - 1
    )

    quickview_close = find_matching(
        report_body,
        quickview_open,
        "(",
        ")"
    )

    if quickview_close == -1:
        return []

    quickview_body = report_body[
        quickview_open + 1:
        quickview_close
    ]

    layout_match = re.search(
        r'\blayout\s*\(',
        quickview_body,
        re.IGNORECASE
    )

    if not layout_match:
        return []

    layout_open = (
        layout_match.end() - 1
    )

    layout_close = find_matching(
        quickview_body,
        layout_open,
        "(",
        ")"
    )

    if layout_close == -1:
        return []

    layout_body = quickview_body[
        layout_open + 1:
        layout_close
    ]

    fields_match = re.search(
        r'\bfields\s*\(',
        layout_body,
        re.IGNORECASE
    )

    if not fields_match:
        return []

    fields_open = (
        fields_match.end() - 1
    )

    fields_close = find_matching(
        layout_body,
        fields_open,
        "(",
        ")"
    )

    if fields_close == -1:
        return []

    fields_body = layout_body[
        fields_open + 1:
        fields_close
    ]

    return extract_fields(
        fields_body
    )


def get_reports(text):

    reports_sections = get_reports_sections(
        text
    )

    if len(reports_sections) < 2:
        return []

    form_section = reports_sections[0]

    report_section = reports_sections[1]

    report_forms = get_report_forms(
        form_section
    )

    results = []

    pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    for match in pattern.finditer(
        report_section
    ):

        report_name = match.group(1)

        open_pos = match.end() - 1

        close_pos = find_matching(
            report_section,
            open_pos,
            "{",
            "}"
        )

        if close_pos == -1:
            continue

        report_body = report_section[
            open_pos + 1:
            close_pos
        ]

        fields = get_quickview_fields(
            report_body
        )

        results.append(
            {
                "report": report_name,
                "form": report_forms.get(
                    report_name,
                    ""
                ),
                "fields": fields
            }
        )

    return results


def main():

    input_file = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "fields.ds"
    )

    output_file = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "reports.json"
    )

    with open(
        input_file,
        "r",
        encoding="utf-8",
        errors="replace"
    ) as file:

        text = file.read()

    results = get_reports(
        text
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False
        )

    total_fields = sum(
        len(item["fields"])
        for item in results
    )

    print(
        "Extracted "
        + str(len(results))
        + " report(s), "
        + str(total_fields)
        + " quickview field(s)."
    )

    print(
        "Output: "
        + output_file
    )


if __name__ == "__main__":
    main()
