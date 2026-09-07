import re
import json
import argparse


def find_matching_brace(text, open_idx):
    depth = 0
    in_string = False
    escaped = False
    in_line_comment = False
    in_block_comment = False

    i = open_idx

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_string:
            if char == "\\" and not escaped:
                escaped = True
            elif char == '"' and not escaped:
                in_string = False
            else:
                escaped = False

            i += 1
            continue

        if char == '"':
            in_string = True
            i += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue

        if char == "{":
            depth += 1

        elif char == "}":
            depth -= 1

            if depth == 0:
                return i

        i += 1

    return -1


def find_script_end(text, start):
    depth = 1
    in_string = False
    escaped = False
    in_line_comment = False
    in_block_comment = False

    i = start

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_string:
            if char == "\\" and not escaped:
                escaped = True
            elif char == '"' and not escaped:
                in_string = False
            else:
                escaped = False

            i += 1
            continue

        if char == '"':
            in_string = True
            i += 1
            continue

        if char == "/" and next_char == "/":
            in_line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            in_block_comment = True
            i += 2
            continue

        if char == "(":
            depth += 1

        elif char == ")":
            depth -= 1

            if depth == 0:
                return i

        i += 1

    return -1


def extract_deluge_script(body):
    match = re.search(
        r'custom\s+deluge\s+script\s*\(',
        body,
        re.IGNORECASE
    )

    if not match:
        return None

    open_idx = body.find("(", match.start())

    if open_idx == -1:
        return None

    script_start = open_idx + 1

    script_end = find_script_end(
        body,
        script_start
    )

    if script_end == -1:
        return None

    script = body[script_start:script_end]

    return script.strip()


def extract_workflows(text):
    workflow_match = re.search(
        r'\bworkflow\s*\{',
        text,
        re.IGNORECASE
    )

    if not workflow_match:
        raise ValueError("No 'workflow' block found in this file")

    wf_open = text.find(
        "{",
        workflow_match.start()
    )

    wf_close = find_matching_brace(
        text,
        wf_open
    )

    if wf_close == -1:
        raise ValueError(
            "Could not find the closing brace of the workflow block"
        )

    workflow_body = text[
        wf_open + 1:wf_close
    ]

    entry_pattern = re.compile(
        r'(\w+)\s+as\s+"([^"]*)"\s*\r?\n\s*\{',
        re.MULTILINE
    )

    results = []

    for em in entry_pattern.finditer(workflow_body):

        ident = em.group(1)
        display = em.group(2)

        brace_idx = workflow_body.find(
            "{",
            em.end() - 1
        )

        if brace_idx == -1:
            continue

        close_idx = find_matching_brace(
            workflow_body,
            brace_idx
        )

        if close_idx == -1:
            continue

        body = workflow_body[
            brace_idx + 1:close_idx
        ]

        def field(pattern):
            match = re.search(
                pattern,
                body,
                re.MULTILINE
            )

            if match:
                return match.group(1).strip()

            return None

        form_name = field(
            r'\bform\s*=\s*([A-Za-z0-9_]+)'
        )

        record_event = field(
            r'\brecord event\s*=\s*([^\n]+)'
        )

        workflow_type = field(
            r'^\s*type\s*=\s*([A-Za-z0-9_]+)'
        )

        deluge_script = extract_deluge_script(body)

        results.append({
            "id": ident,
            "display_name": display,
            "form": form_name,
            "record_event": record_event,
            "type": workflow_type,
            "deluge_script": deluge_script
        })

    return results


def main():

    parser = argparse.ArgumentParser(
        description="Extract Zoho Creator workflows and complete Deluge scripts"
    )

    parser.add_argument(
        "--input",
        default="fields.ds",
        help="Path to the Zoho Creator .ds file"
    )

    parser.add_argument(
        "--output",
        default="workflows_with_form.json",
        help="Path to the output JSON file"
    )

    args = parser.parse_args()

    try:
        with open(
            args.input,
            "r",
            encoding="utf-8"
        ) as f:
            text = f.read()

    except FileNotFoundError:
        print(
            f"Error: File not found: {args.input}"
        )
        return

    except Exception as e:
        print(
            f"Error reading input file: {e}"
        )
        return

    try:
        results = extract_workflows(text)

    except Exception as e:
        print(
            f"Error extracting workflows: {e}"
        )
        return

    try:
        with open(
            args.output,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                results,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:
        print(
            f"Error writing output file: {e}"
        )
        return

    missing_forms = sum(
        1
        for workflow in results
        if not workflow["form"]
    )

    missing_scripts = sum(
        1
        for workflow in results
        if not workflow["deluge_script"]
    )

    print()
    print(
        f"Wrote {len(results)} workflows -> {args.output}"
    )

    print(
        f"Missing forms: {missing_forms}"
    )

    print(
        f"Missing Deluge scripts: {missing_scripts}"
    )

    print()

    for workflow in results:

        script = workflow["deluge_script"]

        if script:
            print(
                f"[OK] {workflow['display_name']}: "
                f"{len(script)} characters"
            )
        else:
            print(
                f"[NO SCRIPT] "
                f"{workflow['display_name']}"
            )


if __name__ == "__main__":
    main()
