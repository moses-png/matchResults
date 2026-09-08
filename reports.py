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


def get_brace_block(text, start):
    open_pos = text.find("{", start)

    if open_pos == -1:
        return None

    close_pos = find_matching_delimiter(
        text,
        open_pos,
        "{",
        "}"
    )

    if close_pos == -1:
        return None

    return text[open_pos + 1:close_pos]


def get_parenthesis_block(text, start):
    open_pos = text.find("(", start)

    if open_pos == -1:
        return None

    close_pos = find_matching_delimiter(
        text,
        open_pos,
        "(",
        ")"
    )

    if close_pos == -1:
        return None

    return text[open_pos + 1:close_pos]


def extract_fields_from_report(report_block):

    quickview_match = re.search(
        r'\bquickview\s*\(',
        report_block,
        re.IGNORECASE
    )

    if not quickview_match:
        return []

    quickview_block = get_parenthesis_block(
        report_block,
        quickview_match.start()
    )

    if quickview_block is None:
        return []

    layout_match = re.search(
        r'\blayout\s*\(',
        quickview_block,
        re.IGNORECASE
    )

    if not layout_match:
        return []

    layout_block = get_parenthesis_block(
        quickview_block,
        layout_match.start()
    )

    if layout_block is None:
        return []

    datablock_match = re.search(
        r'\bdatablock\d*\s*\(',
        layout_block,
        re.IGNORECASE
    )

    if not datablock_match:
        return []

    datablock_block = get_parenthesis_block(
        layout_block,
        datablock_match.start()
    )

    if datablock_block is None:
        return []

    fields_match = re.search(
        r'\bfields\s*\(',
        datablock_block,
        re.IGNORECASE
    )

    if not fields_match:
        return []

    fields_block = get_parenthesis_block(
        datablock_block,
        fields_match.start()
    )

    if fields_block is None:
        return []

    fields = []

    for line in fields_block.splitlines():

        line = line.strip()

        if not line:
            continue

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)'
            r'(?:\s+as\s+"[^"]*")?'
            r'\s*$',
            line,
            re.IGNORECASE
        )

        if match:

            field_name = match.group(1)

            if field_name not in fields:
                fields.append(field_name)

    return fields


def extract_report_definitions(text):

    reports = {}

    reports_matches = list(
        re.finditer(
            r'\breports\s*\{',
            text,
            re.IGNORECASE
        )
    )

    if not reports_matches:
        return reports

    report_section = None

    for match in reports_matches:

        block = get_brace_block(
            text,
            match.start()
        )

        if block is None:
            continue

        if re.search(
            r'\breport\s+[A-Za-z_][A-Za-z0-9_]*\s*\{',
            block,
            re.IGNORECASE
        ):
            report_section = block

    if report_section is None:
        return reports

    report_pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)'
        r'\s*\{',
        re.IGNORECASE
    )

    for match in report_pattern.finditer(report_section):

        report_name = match.group(1)

        report_block = get_brace_block(
            report_section,
            match.start()
        )

        if report_block is None:
            continue

        fields = extract_fields_from_report(
            report_block
        )

        if not fields:
            continue

        reports[report_name] = {
            "report": report_name,
            "fields": fields
        }

    return reports


def extract_menu_structure(text):

    mappings = {}

    menu_match = re.search(
        r'\bmenu\s*\{',
        text,
        re.IGNORECASE
    )

    if not menu_match:
        return mappings

    menu_block = get_brace_block(
        text,
        menu_match.start()
    )

    if menu_block is None:
        return mappings

    section_pattern = re.compile(
        r'\bsection\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)'
        r'\s*\{',
        re.IGNORECASE
    )

    section_matches = list(
        section_pattern.finditer(menu_block)
    )

    for section_match in section_matches:

        section_name = section_match.group(1)

        section_block = get_brace_block(
            menu_block,
            section_match.start()
        )

        if section_block is None:
            continue

        form_pattern = re.compile(
            r'\bform\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)'
            r'\s*\{',
            re.IGNORECASE
        )

        report_pattern = re.compile(
            r'\breport\s+'
            r'([A-Za-z_][A-Za-z0-9_]*)'
            r'\s*\{',
            re.IGNORECASE
        )

        elements = []

        for match in form_pattern.finditer(
            section_block
        ):
            elements.append(
                (
                    match.start(),
                    "form",
                    match.group(1)
                )
            )

        for match in report_pattern.finditer(
            section_block
        ):
            elements.append(
                (
                    match.start(),
                    "report",
                    match.group(1)
                )
            )

        elements.sort(
            key=lambda x: x[0]
        )

        current_form = ""

        for _, element_type, name in elements:

            if element_type == "form":

                current_form = name

            elif element_type == "report":

                mappings[name] = {
                    "section": section_name,
                    "form": current_form
                }

    return mappings


def main():

    print("Reading:", INPUT_FILE)

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        text = file.read()

    print(
        "File size:",
        len(text),
        "characters"
    )

    report_definitions = extract_report_definitions(
        text
    )

    print(
        "Reports with quickview fields:",
        len(report_definitions)
    )

    menu_mappings = extract_menu_structure(
        text
    )

    print(
        "Reports found in menu:",
        len(menu_mappings)
    )

    output = []

    for report_name, report_data in report_definitions.items():

        section = ""
        form = ""

        if report_name in menu_mappings:

            section = menu_mappings[
                report_name
            ]["section"]

            form = menu_mappings[
                report_name
            ]["form"]

        output.append({
            "section": section,
            "form": form,
            "report": report_name,
            "fields": report_data["fields"]
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

    missing_section = [
        item["report"]
        for item in output
        if not item["section"]
    ]

    missing_form = [
        item["report"]
        for item in output
        if not item["form"]
    ]

    print()
    print("====================================")
    print("EXTRACTION COMPLETE")
    print("====================================")
    print(
        "Reports:",
        len(output)
    )
    print(
        "Missing sections:",
        len(missing_section)
    )
    print(
        "Missing forms:",
        len(missing_form)
    )
    print(
        "Output:",
        OUTPUT_FILE
    )

    if missing_section:

        print()
        print("Reports missing sections:")

        for report in missing_section:
            print(" -", report)

    if missing_form:

        print()
        print("Reports missing forms:")

        for report in missing_form:
            print(" -", report)


if __name__ == "__main__":
    main()
