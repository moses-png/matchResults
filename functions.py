from pathlib import Path
import json
import re

INPUT_FILE = Path("fields.ds")
OUTPUT_FILE = Path("functions.json")


def mask_non_code(text):
    out = list(text)
    i = 0
    n = len(text)
    state = "code"

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if state == "code":
            if c == "/" and nxt == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = "line_comment"
                continue

            if c == "/" and nxt == "*":
                out[i] = out[i + 1] = " "
                i += 2
                state = "block_comment"
                continue

            if c == '"':
                out[i] = " "
                i += 1
                state = "double_string"
                continue

            if c == "'":
                out[i] = " "
                i += 1
                state = "single_string"
                continue

            i += 1

        elif state == "line_comment":
            if c == "\n":
                state = "code"
            else:
                out[i] = " "
            i += 1

        elif state == "block_comment":
            if c == "*" and nxt == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = "code"
            else:
                if c != "\n":
                    out[i] = " "
                i += 1

        else:
            quote = '"' if state == "double_string" else "'"

            if c == "\\" and i + 1 < n:
                out[i] = out[i + 1] = " "
                i += 2
            elif c == quote:
                out[i] = " "
                i += 1
                state = "code"
            else:
                if c != "\n":
                    out[i] = " "
                i += 1

    return "".join(out)


def find_matching_brace(masked, start):
    depth = 0

    for i in range(start, len(masked)):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1

            if depth == 0:
                return i

    return -1


def split_params(params):
    params = params.strip()

    if not params:
        return []

    result = []

    for item in params.split(","):
        item = item.strip()

        match = re.match(
            r"(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)$",
            item
        )

        if match:
            result.append({
                "type": match.group(1).strip(),
                "name": match.group(2)
            })
        else:
            result.append({
                "type": "",
                "name": item
            })

    return result


def extract_functions(source):
    masked = mask_non_code(source)

    functions_marker = re.search(
        r"\bfunctions\s*\{",
        masked
    )

    if not functions_marker:
        raise ValueError(
            "Could not find the functions { ... } section in functions.ds"
        )

    start = functions_marker.end()
    functions = []

    signature_pattern = re.compile(
        r"(?m)^[ \t]*"
        r"(?P<return_type>[A-Za-z_][A-Za-z0-9_]*)"
        r"\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
        r"\s*\((?P<params>[^()\n]*)\)"
        r"\s*\{"
    )

    for match in signature_pattern.finditer(masked, start):

        open_brace = masked.find(
            "{",
            match.start(),
            match.end()
        )

        if open_brace == -1:
            continue

        close_brace = find_matching_brace(
            masked,
            open_brace
        )

        if close_brace == -1:
            continue

        full_name = match.group("name")
        return_type = match.group("return_type")
        params_text = match.group("params")

        if "." in full_name:
            namespace, function_name = full_name.rsplit(".", 1)
        else:
            namespace = None
            function_name = full_name

        signature = source[
            match.start():open_brace
        ].strip()

        full_script = source[
            match.start():close_brace + 1
        ].strip()

        body = source[
            open_brace + 1:close_brace
        ].strip()

        start_line = source.count(
            "\n",
            0,
            match.start()
        ) + 1

        end_line = source.count(
            "\n",
            0,
            close_brace
        ) + 1

        functions.append({
            "name": function_name,
            "full_name": full_name,
            "namespace": namespace,
            "return_type": return_type,
            "parameters": split_params(params_text),
            "signature": signature,
            "script": full_script,
            "body": body,
            "start_line": start_line,
            "end_line": end_line
        })

    return functions


def main():
    if not INPUT_FILE.exists():
        raise SystemExit(
            f"ERROR: {INPUT_FILE} was not found."
        )

    source = INPUT_FILE.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    functions = extract_functions(source)

    data = {
        "source_file": INPUT_FILE.name,
        "function_count": len(functions),
        "functions": functions
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(f"Extracted {len(functions)} functions")
    print(f"Created {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
