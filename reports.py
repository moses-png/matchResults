#!/usr/bin/env python3
"""
Parser for fields.ds file - Extracts report names and their fields.
Outputs JSON format like:
{
    "report": "All_Customer_Deposit_Details",
    "fields": ["Customer_Deposit_Number", "Customer_Deposit_Date", ...]
}
"""

import re
import json
import sys
from pathlib import Path


def read_file(filepath: str) -> str:
    """Read the fields.ds file and return its content."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def remove_comments(content: str) -> str:
    """Remove single-line and block comments from the content."""
    # Remove block comments /* ... */
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove single-line comments //
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    return content


def find_matching_brace(content: str, start_pos: int) -> int:
    """
    Given a position of an opening brace '{', find the position of the
    matching closing brace, accounting for nested braces and strings.
    """
    depth = 0
    i = start_pos
    n = len(content)
    in_string = False
    string_char = None

    while i < n:
        ch = content[i]

        # Handle string literals
        if in_string:
            if ch == '\\':
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            i += 1
            continue

        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1

    return -1


def find_matching_paren(content: str, start_pos: int) -> int:
    """Given a position of an opening '(', find matching ')'."""
    depth = 0
    i = start_pos
    n = len(content)
    in_string = False
    string_char = None

    while i < n:
        ch = content[i]

        if in_string:
            if ch == '\\':
                i += 2
                continue
            if ch == string_char:
                in_string = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = True
            string_char = ch
            i += 1
            continue

        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1

    return -1


def extract_fields_block(report_body: str) -> list:
    """
    Extract field names from the `fields ( ... )` block inside a report body.
    Fields look like: `Customer_Deposit_Number as "Customer Deposit Number"`
    or just `Customer`. Nested blocks like `(...)` with displayformat
    should be ignored.
    """
    fields = []

    # Find the `fields` keyword followed by '('
    fields_match = re.search(r'\bfields\s*\(', report_body)
    if not fields_match:
        return fields

    open_paren = fields_match.end() - 1
    close_paren = find_matching_paren(report_body, open_paren)
    if close_paren == -1:
        return fields

    fields_content = report_body[open_paren + 1:close_paren]

    # Walk through the content, skipping over any nested parenthesized blocks
    i = 0
    n = len(fields_content)
    current_line_start = 0

    while i < n:
        ch = fields_content[i]
        if ch == '(':
            # Skip the entire nested block
            close = find_matching_paren(fields_content, i)
            if close == -1:
                break
            i = close + 1
            continue
        i += 1

    # Remove nested paren blocks so we can safely parse field names
    cleaned = []
    i = 0
    while i < n:
        ch = fields_content[i]
        if ch == '(':
            close = find_matching_paren(fields_content, i)
            if close == -1:
                break
            i = close + 1
            continue
        cleaned.append(ch)
        i += 1
    cleaned = ''.join(cleaned)

    # Now split into tokens by whitespace, then find identifiers that
    # precede `as "..."` or are just standalone identifiers.
    # We'll process line by line for clarity.
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Match patterns:
        #   FieldName as "Display Name"
        #   FieldName
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\b(?:\s+as\s+".*?")?\s*$', line)
        if m:
            field_name = m.group(1)
            # Skip reserved keywords
            if field_name.lower() in ('fields', 'as'):
                continue
            fields.append(field_name)

    return fields


def extract_reports(content: str) -> list:
    """
    Extract all reports from the `reports { ... }` block.
    Returns a list of dicts: {"report": name, "fields": [field names]}
    """
    results = []

    # Find the `reports {` block
    reports_match = re.search(r'\breports\s*\{', content)
    if not reports_match:
        return results

    reports_open = reports_match.end() - 1
    reports_close = find_matching_brace(content, reports_open)
    if reports_close == -1:
        return results

    reports_content = content[reports_open + 1:reports_close]

    # Find all `report ReportName { ... }` declarations
    # Supports `default list ReportName {` and `list ReportName {` and `report ReportName {`
    report_pattern = re.compile(
        r'\b(?:default\s+list|list|report)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{'
    )

    pos = 0
    while True:
        m = report_pattern.search(reports_content, pos)
        if not m:
            break

        report_name = m.group(1)
        body_open = m.end() - 1
        body_close = find_matching_brace(reports_content, body_open)
        if body_close == -1:
            break

        report_body = reports_content[body_open + 1:body_close]
        fields = extract_fields_block(report_body)

        results.append({
            "report": report_name,
            "fields": fields
        })

        pos = body_close + 1

    return results


def main():
    # Determine input file
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path("fields.ds")

    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Read and clean content
    content = read_file(str(input_path))
    content = remove_comments(content)

    # Extract reports
    reports = extract_reports(content)

    # Output
    if len(sys.argv) > 2 and sys.argv[2] == "--json-pretty":
        print(json.dumps(reports, indent=4))
    elif len(sys.argv) > 2 and sys.argv[2] == "--json":
        print(json.dumps(reports))
    else:
        # Default: pretty JSON
        print(json.dumps(reports, indent=4))


if __name__ == "__main__":
    main()
