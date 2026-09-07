import re
import json
import argparse

def match_delimiter(s, pos, opening="{", closing="}"):
    depth = 0
    in_string = False
    escaped = False

    for i in range(pos, len(s)):
        c = s[i]

        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            continue

        if c == '"':
            in_string = True
        elif c == opening:
            depth += 1
        elif c == closing:
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

        m = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:as\s+"[^"]*")?\s*$',
            line
        )

        if m:
            fields.append(m.group(1))

    return fields

def parse_ds(text):
    reports_match = re.search(r'\breports\s*\{', text)

    if not reports_match:
        raise ValueError("reports section not found")

    reports_open = text.find("{", reports_match.start())
    reports_close = match_delimiter(text, reports_open)

    if reports_close == -1:
        raise ValueError("Could not parse reports section")

    reports_text = text[reports_open + 1:reports_close]
    output = []

    for report_match in re.finditer(
        r'\bdefault\s+list\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{',
        reports_text
    ):
        report_name = report_match.group(1)

        report_open = reports_text.find("{", report_match.start())
        report_close = match_delimiter(reports_text, report_open)

        if report_close == -1:
            continue

        report_block = reports_text[report_open + 1:report_close]

        source_match = re.search(
            r'\bshow\s+all\s+rows\s+from\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(',
            report_block
        )

        if not source_match:
            continue

        form_name = source_match.group(1)

        fields_open = report_block.find("(", source_match.start())
        fields_close = match_delimiter(
            report_block,
            fields_open,
            "(",
            ")"
        )

        if fields_close == -1:
            continue

        fields = extract_fields(
            report_block[fields_open + 1:fields_close]
        )

        output.append({
            "form": form_name,
            "report": report_name,
            "fields": fields
        })

    return output

def main():
    parser = argparse.ArgumentParser(
        description="Extract Zoho Creator report/form/quick-view fields from a .ds file."
    )

    parser.add_argument(
        "input_ds",
        help="Path to the Zoho Creator .ds file"
    )

    parser.add_argument(
        "-o",
        "--output",
        default="reports.json",
        help="Output JSON filename"
    )

    args = parser.parse_args()

    with open(
        args.input_ds,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:
        text = f.read()

    data = parse_ds(text)

    with open(
        args.output,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(f"Extracted {len(data)} reports")
    print(f"Saved to: {args.output}")

if __name__ == "__main__":
    main()
