import json
import re
import sys


def find_matching(text, open_idx, open_ch, close_ch):
    depth = 0
    i = open_idx

    while i < len(text):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1

    return -1


def extract_block(text, start_from, keyword, open_ch, close_ch):
    pattern = (
        r'\b' + re.escape(keyword) +
        r'\s*' + re.escape(open_ch)
    )

    match = re.search(pattern, text[start_from:])

    if not match:
        return None

    open_idx = start_from + match.end() - 1

    close_idx = find_matching(
        text,
        open_idx,
        open_ch,
        close_ch
    )

    if close_idx == -1:
        return None

    return text[open_idx + 1:close_idx]


def parse_fields_block(fields_text):
    fields = []

    for line in fields_text.splitlines():
        line = line.strip()

        if not line:
            continue

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s+as\s+"(?:[^"\\]|\\.)*")?'
            r'\s*$',
            line
        )

        if match:
            fields.append(match.group(1))

    return fields


def get_reports_section(text):
    match = re.search(
        r'^\s*reports\s*$',
        text,
        re.MULTILINE
    )

    if not match:
        return None

    brace = re.search(
        r'\{',
        text[match.end():]
    )

    if not brace:
        return None

    open_idx = match.end() + brace.start()

    close_idx = find_matching(
        text,
        open_idx,
        '{',
        '}'
    )

    if close_idx == -1:
        return None

    return text[open_idx + 1:close_idx]


def get_report_form_map(text):
    mapping = {}

    forms_section = extract_block(
        text,
        0,
        "forms",
        "{",
        "}"
    )

    if forms_section is None:
        return mapping

    return mapping


def get_report_form_from_list(reports_text):
    mapping = {}

    pattern = re.compile(
        r'\b(?:default\s+list|list)\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.MULTILINE
    )

    for match in pattern.finditer(reports_text):

        report_name = match.group(1)

        open_idx = match.end() - 1

        close_idx = find_matching(
            reports_text,
            open_idx,
            '{',
            '}'
        )

        if close_idx == -1:
            continue

        body = reports_text[
            open_idx + 1:close_idx
        ]

        form_match = re.search(
            r'\bshow\s+all\s+rows\s+from\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)',
            body,
            re.IGNORECASE
        )

        if form_match:
            mapping[report_name] = form_match.group(1)

    return mapping


def get_quickview_fields(report_body):
    quickview = extract_block(
        report_body,
        0,
        "quickview",
        "(",
        ")"
    )

    if quickview is None:
        return []

    layout = extract_block(
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

    search_from = 0

    while True:

        match = re.search(
            r'\bfields\s*\(',
            layout[search_from:],
            re.IGNORECASE
        )

        if not match:
            break

        open_idx = (
            search_from +
            match.end() -
            1
        )

        close_idx = find_matching(
            layout,
            open_idx,
            "(",
            ")"
        )

        if close_idx == -1:
            break

        fields_body = layout[
            open_idx + 1:
            close_idx
        ]

        extracted = parse_fields_block(
            fields_body
        )

        for field in extracted:
            if field not in seen:
                seen.add(field)
                fields.append(field)

        search_from = close_idx + 1

    return fields


def get_reports(text):
    reports_text = get_reports_section(text)

    if reports_text is None:
        return []

    report_to_form = get_report_form_from_list(
        reports_text
    )

    results = []

    pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.MULTILINE
    )

    seen_reports = set()

    for match in pattern.finditer(reports_text):

        report_name = match.group(1)

        if report_name in seen_reports:
            continue

        seen_reports.add(report_name)

        open_idx = match.end() - 1

        close_idx = find_matching(
            reports_text,
            open_idx,
            "{",
            "}"
        )

        if close_idx == -1:
            continue

        report_body = reports_text[
            open_idx + 1:
            close_idx
        ]

        fields = get_quickview_fields(
            report_body
        )

        results.append(
            {
                "report": report_name,
                "form": report_to_form.get(
                    report_name
                ),
                "fields": fields
            }
        )

    return results


def main():

    input_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "fields.ds"
    )

    output_path = (
        sys.argv[2]
        if len(sys.argv) > 2
        else "reports.json"
    )

    with open(
        input_path,
        "r",
        encoding="utf-8",
        errors="replace"
    ) as file:
        text = file.read()

    results = get_reports(text)

    with open(
        output_path,
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
        len(report["fields"])
        for report in results
    )

    reports_without_fields = sum(
        1
        for report in results
        if not report["fields"]
    )

    print(
        f"Extracted {len(results)} report(s), "
        f"{total_fields} quickview field(s) total, "
        f"{reports_without_fields} report(s) without "
        f"quickview fields -> {output_path}"
    )


if __name__ == "__main__":
    main()
