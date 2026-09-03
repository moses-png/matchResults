import re
import json
from pathlib import Path

input_file = Path("fields.ds")
output_file = Path("functions.json")

text = input_file.read_text(
    encoding="utf-8",
    errors="ignore"
)

functions_section = re.search(
    r'\bfunctions\s*\{(.*)\}',
    text,
    re.DOTALL
)

if not functions_section:
    raise ValueError("functions { ... } section not found")

body = functions_section.group(1)

function_pattern = re.compile(
    r'(?m)^\s*'
    r'([A-Za-z_][A-Za-z0-9_]*)\s+'
    r'([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)'
    r'\s*\(([^)]*)\)\s*\{'
)

functions = []

for match in function_pattern.finditer(body):

    return_type = match.group(1)
    full_name = match.group(2)
    parameters_text = match.group(3).strip()

    if "." in full_name:
        namespace, function_name = full_name.rsplit(".", 1)
    else:
        namespace = None
        function_name = full_name

    parameters = []

    if parameters_text:
        for parameter in parameters_text.split(","):
            parameter = parameter.strip()

            parameter_match = re.match(
                r'(.+?)\s+([A-Za-z_][A-Za-z0-9_]*)$',
                parameter
            )

            if parameter_match:
                parameters.append({
                    "type": parameter_match.group(1).strip(),
                    "name": parameter_match.group(2)
                })

    functions.append({
        "name": function_name,
        "full_name": full_name,
        "namespace": namespace,
        "return_type": return_type,
        "parameters": parameters
    })

output_file.write_text(
    json.dumps(
        functions,
        indent=4,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

print(f"Created {output_file}")
print(f"Functions found: {len(functions)}")
