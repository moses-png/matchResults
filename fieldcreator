import re
import json
from pathlib import Path

input_file = Path("fields.ds")
output_file = Path("fields.json")

text = input_file.read_text(encoding="utf-8", errors="ignore")

form_pattern = re.compile(
    r'\bform\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(.*?)\n\s*\}',
    re.DOTALL
)

field_pattern = re.compile(
    r'(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\n?'
)

forms = []

for form_match in form_pattern.finditer(text):
    form_name = form_match.group(1)
    body = form_match.group(2)

    fields = []

    for field_match in field_pattern.finditer(body):
        field_name = field_match.group(1)

        start = field_match.end()
        remainder = body[start:start + 300]

        type_match = re.search(
            r'\btype\s*=\s*([A-Za-z_][A-Za-z0-9_]*)',
            remainder
        )

        field_type = type_match.group(1) if type_match else None

        if field_type == "section":
            continue

        fields.append(field_name)

    forms.append({
        "form": form_name,
        "fields": fields
    })

output_file.write_text(
    json.dumps(forms, indent=4, ensure_ascii=False),
    encoding="utf-8"
)

print(f"Created {output_file}")
