import json
import re
import sys


def find_matching(text, open_idx, open_ch, close_ch):
    """Given the index of an opening bracket in text, return the index of
    its matching closing bracket, respecting nesting. Returns -1 if not found."""
    depth = 0
    i = open_idx
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_block(text, start_from, keyword_pattern, open_ch, close_ch):
    """Find `keyword_pattern` followed by `open_ch` at/after start_from, and
    return (block_inner_text, match_object) or (None, None)."""
    m = re.search(keyword_pattern + r'\s*' + re.escape(open_ch), text[start_from:])
    if not m:
        return None, None
    open_idx = start_from + m.end() - 1
    close_idx = find_matching(text, open_idx, open_ch, close_ch)
    if close_idx == -1:
        return None, None
    return text[open_idx + 1:close_idx], m


def get_top_level_sections(text):
    """Return {section_name: section_body} for every section indented with
    exactly one tab (optionally one leading space), e.g. forms, reports,
    web, phone, tablet, translation. Excludes deeper-nested blocks that
    happen to share the same keyword (e.g. a "reports" block nested
    inside "web")."""
    sections = {}
    for m in re.finditer(r'^ ?\t([A-Za-z_]+)[ \t]*$', text, re.MULTILINE):
        name = m.group(1)
        brace_search = re.search(r'\{', text[m.end():])
        if not brace_search:
            continue
        open_idx = m.end() + brace_search.start()
        close_idx = find_matching(text, open_idx, '{', '}')
        if close_idx == -1:
            continue
        # Keep the first occurrence of each name (there's normally only one
        # top-level section per name anyway).
        sections.setdefault(name, text[open_idx + 1:close_idx])
    return sections


def parse_fields_block(fields_text):
    """Parse the raw contents of a `fields ( ... )` block into a list of
    field names only (the `as "Display Name"` part, if present, is
    discarded). Handles both:
        Field_Name
        Field_Name as "Display Name"
    """
    fields = []
    for raw_line in fields_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:as\s+"(?:[^"\\]|\\.)*")?\s*$', line)
        if m:
            fields.append(m.group(1))
    return fields


def get_report_form_map(reports_section_body):
    """Parse the top-level `reports { ... }` section to map
    report_name -> form_name, using the `show all rows from FORM` line."""
    mapping = {}
    for entry_match in re.finditer(r'\b(?:default list|list)\s+(\w+)\s*\{', reports_section_body):
        report_name = entry_match.group(1)
        open_idx = entry_match.end() - 1
        close_idx = find_matching(reports_section_body, open_idx, '{', '}')
        if close_idx == -1:
            continue
        report_body = reports_section_body[open_idx + 1:close_idx]
        form_match = re.search(r'show all rows from\s+(\w+)', report_body)
        if form_match:
            mapping[report_name] = form_match.group(1)
    return mapping


def get_report_fields_map(device_section_body):
    """Parse a device-view section's nested `reports { report NAME { ...
    detailview(layout(datablock1(fields(...)))) ... } }` structure to map
    report_name -> list of field names."""
    mapping = {}
    reports_body, _ = extract_block(device_section_body, 0, r'\breports\b', '{', '}')
    if reports_body is None:
        return mapping

    for entry_match in re.finditer(r'\breport\s+(\w+)\s*\{', reports_body):
        report_name = entry_match.group(1)
        open_idx = entry_match.end() - 1
        close_idx = find_matching(reports_body, open_idx, '{', '}')
        if close_idx == -1:
            continue
        report_body = reports_body[open_idx + 1:close_idx]

        dv_body, _ = extract_block(report_body, 0, r'\bdetailview\b', '(', ')')
        if dv_body is None:
            continue
        layout_body, _ = extract_block(dv_body, 0, r'\blayout\b', '(', ')')
        if layout_body is None:
            continue

        # The layout normally holds a single "datablock1 ( fields ( ... ) )",
        # but some reports split their detail view across several data
        # blocks (datablock1, datablock2, ...). Collect fields from every
        # `fields ( ... )` block under this layout, in order, deduplicating
        # by field name (a field can be repeated across panels).
        fields = []
        seen = set()
        search_from = 0
        while True:
            fm = re.search(r'\bfields\s*\(', layout_body[search_from:])
            if not fm:
                break
            open_idx = search_from + fm.end() - 1
            close_idx = find_matching(layout_body, open_idx, '(', ')')
            if close_idx == -1:
                break
            fields_body = layout_body[open_idx + 1:close_idx]
            for name in parse_fields_block(fields_body):
                if name not in seen:
                    seen.add(name)
                    fields.append(name)
            search_from = close_idx + 1

        if fields:
            mapping[report_name] = fields
    return mapping


def extract_reports(text):
    sections = get_top_level_sections(text)

    report_to_form = {}
    if 'reports' in sections:
        report_to_form = get_report_form_map(sections['reports'])

    # Prefer "web" view fields, then fall back to phone/tablet if a report's
    # detailview fields weren't found there.
    report_to_fields = {}
    for device in ('web', 'phone', 'tablet'):
        if device not in sections:
            continue
        device_fields = get_report_fields_map(sections[device])
        for report_name, fields in device_fields.items():
            report_to_fields.setdefault(report_name, fields)

    all_report_names = set(report_to_form) | set(report_to_fields)

    results = []
    for report_name in sorted(all_report_names):
        results.append({
            "report": report_name,
            "form": report_to_form.get(report_name),
            "fields": report_to_fields.get(report_name, []),
        })
    return results


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else 'fields.ds'
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'reports.json'

    with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    results = extract_reports(text)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total_fields = sum(len(r["fields"]) for r in results)
    missing_fields = sum(1 for r in results if not r["fields"])
    print(f"Extracted {len(results)} report(s), {total_fields} field entries total "
          f"({missing_fields} report(s) had no detailview fields found) -> {output_path}")


if __name__ == '__main__':
    main()
