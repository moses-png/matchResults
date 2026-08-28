
import re
import json
import argparse


def find_matching_brace(s, open_idx):
    depth = 0

    for i in range(open_idx, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1

            if depth == 0:
                return i

    return -1


def extract_deluge_script(body):
    ds_match = re.search(r'custom deluge script\s*\(', body)

    if not ds_match:
        return None

    popen = body.index('(', ds_match.start())

    depth = 0
    in_string = False
    escaped = False

    for i in range(popen, len(body)):
        char = body[i]

        if char == '"' and not escaped:
            in_string = not in_string

        if not in_string:
            if char == '(':
                depth += 1

            elif char == ')':
                depth -= 1

                if depth == 0:
                    script = body[popen + 1:i]
                    return " ".join(script.split())

        if char == '\\' and not escaped:
            escaped = True
        else:
            escaped = False

    return None


def extract_workflows(text):
    workflow_match = re.search(r'\bworkflow\s*\{', text)

    if not workflow_match:
        raise ValueError("No 'workflow' block found in this file")

    wf_open = text.index('{', workflow_match.start())

    wf_close = find_matching_brace(text, wf_open)

    if wf_close == -1:
        raise ValueError("Could not find the closing brace of the workflow block")

    workflow_body = text[wf_open + 1:wf_close]

    entry_pattern = re.compile(
        r'(\w+)\s+as\s+"([^"]*)"\s*\r?\n\s*\{'
    )

    results = []

    for em in entry_pattern.finditer(workflow_body):
        ident = em.group(1)
        display = em.group(2)

        brace_idx = workflow_body.index('{', em.end() - 1)

        close_idx = find_matching_brace(workflow_body, brace_idx)

        if close_idx == -1:
            continue

        body = workflow_body[brace_idx + 1:close_idx]

        def field(pattern):
            match = re.search(pattern, body, re.MULTILINE)
            return match.group(1).strip() if match else None

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
    ap = argparse.ArgumentParser(
        description="Extract workflows from a Zoho Creator .ds file"
    )

    ap.add_argument(
        "--input",
        default="Clean_Sand_Management.ds",
        help="Path to the input .ds file"
    )

    ap.add_argument(
        "--output",
        default="workflows_with_form.json",
        help="Path to the output JSON file"
    )

    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()

    except FileNotFoundError:
        print(f"Error: File not found: {args.input}")
        print("Put the .ds file in the same folder as this Python script.")
        return

    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    try:
        results = extract_workflows(text)

    except Exception as e:
        print(f"Error extracting workflows: {e}")
        return

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(
                results,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:
        print(f"Error writing output file: {e}")
        return

    missing = sum(
        1 for workflow in results
        if not workflow["form"]
    )

    missing_script = sum(
        1 for workflow in results
        if not workflow["deluge_script"]
    )

    print(f"Wrote {len(results)} workflows -> {args.output}")

    if missing:
        print(
            f"Warning: {missing} workflows had no 'form' value detected"
        )

    if missing_script:
        print(
            f"Warning: {missing_script} workflows had no Deluge script detected"
        )


if __name__ == "__main__":
    main()
