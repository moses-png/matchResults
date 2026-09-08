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


def get_block(text, start, opening, closing):
    open_pos = text.find(opening, start)

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
            report_forms[report_name] = form_match.group(1)

    return report_forms


def extract_menu_report_forms(text):
    report_forms = {}

    menu_pattern = re.compile(
        r'\bmenu\s*\{',
        re.IGNORECASE
    )

    for menu_match in menu_pattern.finditer(text):

        menu_open = text.find(
            "{",
            menu_match.start()
        )

        menu_end = find_matching_delimiter(
            text,
            menu_open,
            "{",
            "}"
        )

        if menu_end == -1:
            continue

        menu_block = text[
            menu_open + 1:menu_end
        ]

        tokens = []

        token_pattern = re.compile(
            r'\bform\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{'
            r'|'
            r'\breport\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{',
            re.IGNORECASE
        )

        for token in token_pattern.finditer(menu_block):

            form_name = token.group(1)
            report_name = token.group(2)

            if form_name:
                tokens.append(
                    (
                        token.start(),
                        "form",
                        form_name
                    )
                )

            elif report_name:
                tokens.append(
                    (
                        token.start(),
                        "report",
                        report_name
                    )
                )

        current_form = None

        for _, token_type, name in tokens:

            if token_type == "form":
                current_form = name

            elif token_type == "report":

                if current_form:
                    report_forms[name] = current_form

    return report_forms


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


def extract_reports(text):
    reports = {}

    report_pattern = re.compile(
        r'\breport\s+'
        r'([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        re.IGNORECASE
    )

    for match in report_pattern.finditer(text):

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

        report_block = text[
            open_pos + 1:close_pos
        ]

        fields = extract_report_fields(
            report_block
        )

        if not fields:
            continue

        reports[report_name] = {
            "report": report_name,
            "fields": fields
        }

    return reports


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
        "Forms found from default lists:",
        len(default_forms)
    )

    menu_forms = extract_menu_report_forms(
        text
    )

    print(
        "Report/form relationships found from menus:",
        len(menu_forms)
    )

    reports = extract_reports(
        text
    )

    print(
        "Reports with quickview fields:",
        len(reports)
    )

    output = []

    for report_name, report_data in reports.items():

        form_name = ""

        if report_name in menu_forms:
            form_name = menu_forms[report_name]

        elif report_name in default_forms:
            form_name = default_forms[report_name]

        output.append({
            "form": form_name,
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

    missing_forms = [
        item["report"]
        for item in output
        if not item["form"]
    ]

    print()
    print("================================")
    print("Finished")
    print("================================")
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
