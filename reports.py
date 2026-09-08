import re
import json

INPUT_FILE = "fields.ds"
OUTPUT_FILE = "reports.json"


def match_delimiter(text, start, opening, closing):
    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):
        char = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1

            if depth == 0:
                return i

    return -1


def extract_block(text, start, opening, closing):
    open_pos = text.find(opening, start)

    if open_pos == -1:
        return None

    close_pos = match_delimiter(
        text,
        open_pos,
        opening,
        closing
    )

    if close_pos == -1:
        return None

    return text[open_pos + 1:close_pos]


def extract_fields(fields_block):
    fields = []

    pattern = re.compile(
        r'^\s*'
        r'([A-Za-z_][A-Za-z0-9_]*)'
        r'\s*'
        r'(?:as\s+"[^"]*")?'
        r'\s*$'
    )

    for line in fields_block.splitlines():
        line = line.strip()

        if not line:
            continue

        match = pattern.match(line)

        if match:
            field_name = match.group(1)

            if field_name not in fields:
                fields.append(field_name)

    return fields


def extract_default_report_forms(text):
    report_forms = {}

    reports_match = re.search(
        r'\breports\s*\{',
        text
    )

    if not reports_match:
        return report_forms

    reports_end = match_delimiter(
        text,
        text.find("{", reports_match.start()),
        "{",
        "}"
    )

    if reports_end == -1:
        return report_forms

    reports_section = text[
        reports_match.start():reports_end + 1
    ]

    pattern = re.compile(
        r'\bdefault\s+list\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{'
    )

    for match in pattern.finditer(reports_section):

        report_name = match.group(1)

        block_end = match_delimiter(
            reports_section,
            reports_section.find("{", match.start()),
            "{",
            "}"
        )

        if block_end == -1:
            continue

        block = reports_section[
            match.start():block_end + 1
        ]

        form_match = re.search(
            r'\bshow\s+all\s+rows\s+from\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)',
            block,
            re.IGNORECASE
        )

        if form_match:
            report_forms[report_name] = form_match.group(1)

    return report_forms


def extract_reports(text):
    reports = []

    reports_match = re.search(
        r'\breports\s*\{',
        text
    )

    if not reports_match:
        raise ValueError("Could not find the reports section.")

    reports_open = text.find(
        "{",
        reports_match.start()
    )

    reports_end = match_delimiter(
        text,
        reports_open,
        "{",
        "}"
    )

    if reports_end == -1:
        raise ValueError("Could not find the end of the reports section.")

    reports_section = text[
        reports_open + 1:reports_end
    ]

    report_pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{'
    )

    report_matches = list(
        report_pattern.finditer(reports_section)
    )

    for report_match in report_matches:

        report_name = report_match.group(1)

        report_open = reports_section.find(
            "{",
            report_match.start()
        )

        report_end = match_delimiter(
            reports_section,
            report_open,
            "{",
            "}"
        )

        if report_end == -1:
            continue

        report_block = reports_section[
            report_open + 1:report_end
        ]

        quickview_match = re.search(
            r'\bquickview\s*\(',
            report_block,
            re.IGNORECASE
        )

        if not quickview_match:
            continue

        quickview_open = report_block.find(
            "(",
            quickview_match.start()
        )

        quickview_end = match_delimiter(
            report_block,
            quickview_open,
            "(",
            ")"
        )

        if quickview_end == -1:
            continue

        quickview_block = report_block[
            quickview_open + 1:quickview_end
        ]

        layout_match = re.search(
            r'\blayout\s*\(',
            quickview_block,
            re.IGNORECASE
        )

        if not layout_match:
            continue

        layout_open = quickview_block.find(
            "(",
            layout_match.start()
        )

        layout_end = match_delimiter(
            quickview_block,
            layout_open,
            "(",
            ")"
        )

        if layout_end == -1:
            continue

        layout_block = quickview_block[
            layout_open + 1:layout_end
        ]

        datablock_match = re.search(
            r'\bdatablock\d*\s*\(',
            layout_block,
            re.IGNORECASE
        )

        if not datablock_match:
            continue

        datablock_open = layout_block.find(
            "(",
            datablock_match.start()
        )

        datablock_end = match_delimiter(
            layout_block,
            datablock_open,
            "(",
            ")"
        )

        if datablock_end == -1:
            continue

        datablock_block = layout_block[
            datablock_open + 1:datablock_end
        ]

        fields_match = re.search(
            r'\bfields\s*\(',
            datablock_block,
            re.IGNORECASE
        )

        if not fields_match:
            continue

        fields_open = datablock_block.find(
            "(",
            fields_match.start()
        )

        fields_end = match_delimiter(
            datablock_block,
            fields_open,
            "(",
            ")"
        )

        if fields_end == -1:
            continue

        fields_block = datablock_block[
            fields_open + 1:fields_end
        ]

        fields = extract_fields(fields_block)

        reports.append({
            "report": report_name,
            "fields": fields
        })

    return reports


def main():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        text = file.read()

    report_forms = extract_default_report_forms(text)

    reports = extract_reports(text)

    output = []

    for report in reports:

        report_name = report["report"]

        output.append({
            "form": report_forms.get(report_name, ""),
            "report": report_name,
            "fields": report["fields"]
        })

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"Generated {len(output)} reports "
        f"into {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
