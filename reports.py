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


def extract_sections(text):
    sections = []

    section_pattern = re.compile(
        r'\bsection\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    for match in section_pattern.finditer(text):

        section_name = match.group(1)

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

        section_block = text[
            open_pos + 1:close_pos
        ]

        sections.append({
            "section": section_name,
            "block": section_block
        })

    return sections


def extract_reports_from_section(section_name, section_block):
    results = []

    form_pattern = re.compile(
        r'\bform\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    form_matches = list(
        form_pattern.finditer(section_block)
    )

    report_pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    report_matches = list(
        report_pattern.finditer(section_block)
    )

    elements = []

    for match in form_matches:
        elements.append((
            match.start(),
            "form",
            match
        ))

    for match in report_matches:
        elements.append((
            match.start(),
            "report",
            match
        ))

    elements.sort(
        key=lambda x: x[0]
    )

    current_form = None

    for _, element_type, match in elements:

        name = match.group(1)

        if element_type == "form":

            current_form = name

            continue

        report_open = section_block.find(
            "{",
            match.start()
        )

        report_end = find_matching_delimiter(
            section_block,
            report_open,
            "{",
            "}"
        )

        if report_end == -1:
            continue

        report_block = section_block[
            report_open + 1:report_end
        ]

        fields = extract_report_fields(
            report_block
        )

        if not fields:
            continue

        results.append({
            "section": section_name,
            "form": current_form or "",
            "report": name,
            "fields": fields
        })

    return results


def extract_default_list_forms(text):
    report_forms = {}

    pattern = re.compile(
        r'\bdefault\s+list\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    for match in pattern.finditer(text):

        report_name = match.group(1)

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

        block = text[
            open_pos + 1:close_pos
        ]

        form_match = re.search(
            r'\bshow\s+all\s+rows\s+from\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)',
            block,
            re.IGNORECASE
        )

        if form_match:
            report_forms[report_name] = (
                form_match.group(1)
            )

    return report_forms


def main():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        text = file.read()

    print("Reading:", INPUT_FILE)

    default_forms = extract_default_list_forms(
        text
    )

    print(
        "Default-list report/form mappings:",
        len(default_forms)
    )

    sections = extract_sections(
        text
    )

    print(
        "Sections found:",
        len(sections)
    )

    output = []

    seen_reports = set()

    for section_data in sections:

        section_name = section_data["section"]
        section_block = section_data["block"]

        section_reports = extract_reports_from_section(
            section_name,
            section_block
        )

        for report in section_reports:

            report_name = report["report"]

            if report_name in seen_reports:
                continue

            seen_reports.add(
                report_name
            )

            if not report["form"]:

                if report_name in default_forms:
                    report["form"] = (
                        default_forms[report_name]
                    )

            output.append(report)

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

    missing_forms = [
        item["report"]
        for item in output
        if not item["form"]
    ]

    print()
    print("================================")
    print("Finished")
    print("================================")
    print("Sections:", len(sections))
    print("Reports:", len(output))
    print("Missing forms:", len(missing_forms))
    print("Output:", OUTPUT_FILE)

    if missing_forms:

        print()
        print("Reports still missing form names:")

        for report_name in missing_forms:
            print(" -", report_name)


if __name__ == "__main__":
    main()
