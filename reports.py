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


def get_block(text, start, keyword, opening, closing):
    pattern = (
        r'\b' +
        re.escape(keyword) +
        r'\s*' +
        re.escape(opening)
    )

    match = re.search(
        pattern,
        text[start:],
        re.IGNORECASE
    )

    if not match:
        return None

    open_pos = start + match.end() - 1

    close_pos = find_matching(
        text,
        open_pos,
        opening,
        closing
    )

    if close_pos == -1:
        return None

    return text[
        open_pos + 1:
        close_pos
    ]


def extract_fields(fields_text):
    fields = []

    for raw_line in fields_text.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s+as\s+"(?:[^"\\]|\\.)*")?'
            r'\s*$',
            line,
            re.IGNORECASE
        )

        if match:
            fields.append(
                match.group(1)
            )

    return fields


def get_quickview_fields(report_body):
    quickview = get_block(
        report_body,
        0,
        "quickview",
        "(",
        ")"
    )

    if quickview is None:
        return []

    layout = get_block(
        quickview,
        0,
        "layout",
        "(",
        ")"
    )

    if layout is None:
        return []

    fields = []
    seen = set()

    position = 0

    while True:

        match = re.search(
            r'\bfields\s*\(',
            layout[position:],
            re.IGNORECASE
        )

        if not match:
            break

        open_pos = (
            position +
            match.end() -
            1
        )

        close_pos = find_matching(
            layout,
            open_pos,
            "(",
            ")"
        )

        if close_pos == -1:
            break

        fields_body = layout[
            open_pos + 1:
            close_pos
        ]

        extracted = extract_fields(
            fields_body
        )

        for field in extracted:

            if field not in seen:
                seen.add(field)
                fields.append(field)

        position = close_pos + 1

    return fields


def get_report_forms(text):
    result = {}

    pattern = re.compile(
        r'\b(?:default\s+list|list)\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    for match in pattern.finditer(text):

        report_name = match.group(1)

        open_pos = match.end() - 1

        close_pos = find_matching(
            text,
            open_pos,
            "{",
            "}"
        )

        if close_pos == -1:
            continue

        body = text[
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
            result[report_name] = (
                form_match.group(1)
            )

    return result


def get_reports(text):
    report_forms = get_report_forms(text)

    results = []

    pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    seen = set()

    for match in pattern.finditer(text):

        report_name = match.group(1)

        if report_name in seen:
            continue

        open_pos = match.end() - 1

        close_pos = find_matching(
            text,
            open_pos,
            "{",
            "}"
        )

        if close_pos == -1:
            continue

        report_body = text[
            open_pos + 1:
            close_pos
        ]

        fields = get_quickview_fields(
            report_body
        )

        seen.add(report_name)

        results.append(
            {
                "report": report_name,
                "form": report_forms.get(
                    report_name
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

    results = get_reports(text)

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

    no_fields = sum(
        1
        for item in results
        if not item["fields"]
    )

    print(
        "Extracted "
        + str(len(results))
        + " report(s), "
        + str(total_fields)
        + " quickview field(s). "
        + str(no_fields)
        + " report(s) had no quickview fields."
    )

    print(
        "Output: "
        + output_file
    )


if __name__ == "__main__":
    main()
