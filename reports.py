import re
import json

INPUT_FILE = "fields.ds"
OUTPUT_FILE = "reports.json"


def match_delimiter(text, position, opening="{", closing="}"):
    depth = 0
    in_string = False
    escaped = False

    for i in range(position, len(text)):
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


def extract_fields(field_block):
    fields = []

    for line in field_block.splitlines():
        line = re.sub(r'//.*$', '', line).strip()

        if not line:
            continue

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:as\s+"[^"]*")?\s*$',
            line
        )

        if match:
            fields.append(match.group(1))

    return fields


def parse_ds(text):
    reports_match = re.search(
        r'\breports\s*\{',
        text
    )

    if not reports_match:
        raise ValueError("Reports section not found")

    reports_open = text.find(
        "{",
        reports_match.start()
    )

    reports_close = match_delimiter(
        text,
        reports_open
    )

    if reports_close == -1:
        raise ValueError("Could not parse reports section")

    reports_text = text[
        reports_open + 1:
        reports_close
    ]

    output = []

    for report_match in re.finditer(
        r'\bdefault\s+list\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        reports_text
    ):
        report_name = report_match.group(1)

        report_open = reports_text.find(
            "{",
            report_match.start()
        )

        report_close = match_delimiter(
            reports_text,
            report_open
        )

        if report_close == -1:
            continue

        report_block = reports_text[
            report_open + 1:
            report_close
        ]

        source_match = re.search(
            r'\bshow\s+all\s+rows\s+from\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(',
            report_block
        )

        if not source_match:
            continue

        form_name = source_match.group(1)

        fields_open = report_block.find(
            "(",
            source_match.start()
        )

        fields_close = match_delimiter(
            report_block,
            fields_open,
            "(",
            ")"
        )

        if fields_close == -1:
            continue

        fields_block = report_block[
            fields_open + 1:
            fields_close
        ]

        fields = extract_fields(fields_block)

        output.append({
            "form": form_name,
            "report": report_name,
            "fields": fields
        })

    return output


def main():
    print(f"Reading: {INPUT_FILE}")

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as file:
        text = file.read()

    data = parse_ds(text)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"Extracted {len(data)} reports")
    print(f"Generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

