import json
import re
import sys


def find_matching(text, start, opening, closing):
    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True

        elif ch == opening:
            depth += 1

        elif ch == closing:
            depth -= 1

            if depth == 0:
                return i

    return -1


def get_reports_section(text):

    match = re.search(
        r'(?m)^[ \t]*reports[ \t]*\{',
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    open_pos = text.find(
        "{",
        match.start(),
        match.end()
    )

    close_pos = find_matching(
        text,
        open_pos,
        "{",
        "}"
    )

    if close_pos == -1:
        return None

    return text[
        open_pos + 1:
        close_pos
    ]


def get_quickview(report_body):

    match = re.search(
        r'\bquickview\s*\(',
        report_body,
        re.IGNORECASE
    )

    if not match:
        return None

    open_pos = match.end() - 1

    close_pos = find_matching(
        report_body,
        open_pos,
        "(",
        ")"
    )

    if close_pos == -1:
        return None

    return report_body[
        open_pos + 1:
        close_pos
    ]


def get_fields_from_quickview(quickview):

    if quickview is None:
        return []

    layout_match = re.search(
        r'\blayout\s*\(',
        quickview,
        re.IGNORECASE
    )

    if not layout_match:
        return []

    layout_open = layout_match.end() - 1

    layout_close = find_matching(
        quickview,
        layout_open,
        "(",
        ")"
    )

    if layout_close == -1:
        return []

    layout = quickview[
        layout_open + 1:
        layout_close
    ]

    fields_match = re.search(
        r'\bfields\s*\(',
        layout,
        re.IGNORECASE
    )

    if not fields_match:
        return []

    fields_open = fields_match.end() - 1

    fields_close = find_matching(
        layout,
        fields_open,
        "(",
        ")"
    )

    if fields_close == -1:
        return []

    fields_body = layout[
        fields_open + 1:
        fields_close
    ]

    fields = []

    for line in fields_body.splitlines():

        line = line.strip()

        if not line:
            continue

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s+as\s+"[^"]*")?$',
            line,
            re.IGNORECASE
        )

        if match:
            fields.append(
                match.group(1)
            )

    return fields


def extract_reports(text):

    reports_section = get_reports_section(text)

    if reports_section is None:
        print("ERROR: reports section not found")
        return []

    results = []

    pattern = re.compile(
        r'(?m)^[ \t]*report[ \t]+'
        r'([A-Za-z_][A-Za-z0-9_]*)'
        r'[ \t]*\{'
    )

    for match in pattern.finditer(
        reports_section
    ):

        report_name = match.group(1)

        open_pos = match.end() - 1

        close_pos = find_matching(
            reports_section,
            open_pos,
            "{",
            "}"
        )

        if close_pos == -1:
            print(
                "WARNING: Could not close report:",
                report_name
            )
            continue

        report_body = reports_section[
            open_pos + 1:
            close_pos
        ]

        quickview = get_quickview(
            report_body
        )

        fields = get_fields_from_quickview(
            quickview
        )

        results.append(
            {
                "report": report_name,
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

    results = extract_reports(text)

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

    print(
        "Extracted:",
        len(results),
        "reports"
    )

    print(
        "Output:",
        output_file
    )

    for item in results:

        if item["report"] in [
            "All_Payment_Receipt_Vouchers",
            "Payment_Receipt_Vouchers"
        ]:

            print(
                item["report"],
                "=>",
                len(item["fields"]),
                "fields"
            )


if __name__ == "__main__":
    main()
