import re
import json

INPUT_FILE = "fields.ds"
OUTPUT_FILE = "reports.json"


def find_matching_delimiter(text, start, opening, closing):
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


def get_block(text, keyword_position, opening, closing):
    open_pos = text.find(opening, keyword_position)

    if open_pos == -1:
        return None

    close_pos = find_matching_delimiter(
        text,
        open_pos,
        opening,
        closing
    )

    if close_pos == -1:
        return None

    return text[open_pos + 1:close_pos]


def find_reports_sections(text):
    sections = []

    pattern = re.compile(
        r'\breports\s*\{',
        re.IGNORECASE
    )

    for match in pattern.finditer(text):

        open_pos = text.find(
            "{",
            match.start()
        )

        close_pos = find_matching_delimiter(
            text,
            open_pos,
            "{",
            "}"
        )

        if close_pos == -1:
            continue

        sections.append(
            text[open_pos + 1:close_pos]
        )

    return sections


def extract_default_report_forms(text):
    report_forms = {}

    sections = find_reports_sections(text)

    for section in sections:

        pattern = re.compile(
            r'\bdefault\s+list\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
            re.IGNORECASE
        )

        for match in pattern.finditer(section):

            report_name = match.group(1)

            open_pos = section.find(
                "{",
                match.start()
            )

            close_pos = find_matching_delimiter(
                section,
                open_pos,
                "{",
                "}"
            )

            if close_pos == -1:
                continue

            block = section[
                open_pos + 1:close_pos
            ]

            form_match = re.search(
                r'\bshow\s+all\s+rows\s+from\s+'
                r'([A-Za-z_][A-Za-z0-9_]*)',
                block,
                re.IGNORECASE
            )

            if form_match:

                form_name = form_match.group(1)

                report_forms[report_name] = form_name

    return report_forms


def extract_fields(fields_block):
    fields = []

    for line in fields_block.splitlines():

        line = line.strip()

        if not line:
            continue

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)'
            r'\s*(?:as\s+"[^"]*")?\s*$',
            line,
            re.IGNORECASE
        )

        if match:

            field_name = match.group(1)

            if field_name not in fields:
                fields.append(field_name)

    return fields


def extract_report_fields(report_block):
    quickview_match = re.search(
        r'\bquickview\s*\(',
        report_block,
        re.IGNORECASE
    )

    if not quickview_match:
        return []

    quickview_open = report_block.find(
        "(",
        quickview_match.start()
    )

    quickview_end = find_matching_delimiter(
        report_block,
        quickview_open,
        "(",
        ")"
    )

    if quickview_end == -1:
        return []

    quickview_block = report_block[
        quickview_open + 1:quickview_end
    ]

    layout_match = re.search(
        r'\blayout\s*\(',
        quickview_block,
        re.IGNORECASE
    )

    if not layout_match:
        return []

    layout_open = quickview_block.find(
        "(",
        layout_match.start()
    )

    layout_end = find_matching_delimiter(
        quickview_block,
        layout_open,
        "(",
        ")"
    )

    if layout_end == -1:
        return []

    layout_block = quickview_block[
        layout_open + 1:layout_end
    ]

    datablock_match = re.search(
        r'\bdatablock\d*\s*\(',
        layout_block,
        re.IGNORECASE
    )

    if not datablock_match:
        return []

    datablock_open = layout_block.find(
        "(",
        datablock_match.start()
    )

    datablock_end = find_matching_delimiter(
        layout_block,
        datablock_open,
        "(",
        ")"
    )

    if datablock_end == -1:
        return []

    datablock_block = layout_block[
        datablock_open + 1:datablock_end
    ]

    fields_match = re.search(
        r'\bfields\s*\(',
        datablock_block,
        re.IGNORECASE
    )

    if not fields_match:
        return []

    fields_open = datablock_block.find(
        "(",
        fields_match.start()
    )

    fields_end = find_matching_delimiter(
        datablock_block,
        fields_open,
        "(",
        ")"
    )

    if fields_end == -1:
        return []

    fields_block = datablock_block[
        fields_open + 1:fields_end
    ]

    return extract_fields(fields_block)


def extract_reports(text):
    reports = []

    sections = find_reports_sections(text)

    report_pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    for section in sections:

        matches = list(
            report_pattern.finditer(section)
        )

        for match in matches:

            report_name = match.group(1)

            open_pos = section.find(
                "{",
                match.start()
            )

            close_pos = find_matching_delimiter(
                section,
                open_pos,
                "{",
                "}"
            )

            if close_pos == -1:
                continue

            report_block = section[
                open_pos + 1:close_pos
            ]

            fields = extract_report_fields(
                report_block
            )

            if fields:

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

    report_forms = extract_default_report_forms(
        text
    )

    reports = extract_reports(
        text
    )

    output = []

    seen = set()

    for report in reports:

        report_name = report["report"]

        if report_name in seen:
            continue

        seen.add(report_name)

        output.append({
            "form": report_forms.get(
                report_name,
                ""
            ),
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
        "Reports found:",
        len(output)
    )

    print(
        "Output:",
        OUTPUT_FILE
    )

    for report in output:

        print(
            report["form"],
            "->",
            report["report"],
            "->",
            len(report["fields"]),
            "fields"
        )


if __name__ == "__main__":
    main()
