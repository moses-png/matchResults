from pathlib import Path
import re
import json
from typing import Dict, List, Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "fields.ds"
OUTPUT_FILE = BASE_DIR / "functions.json"


class DelugeFunctionExtractor:

    def __init__(self):
        self.patterns = {
            "void": r"void\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "map": r"map\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "string": r"string\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "int": r"int\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "float": r"float\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "boolean": r"boolean\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "list": r"list\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "date": r"date\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "datetime": r"datetime\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "number": r"number\s+([.\w]+)\s*\(([^)]*)\s*\{([\s\S]*?)\n\s*\}",
            "time": r"time\s+([.\w]+)\s*\(([^)]*)\s*\{([\s\S]*?)\n\s*\}",
        }

    def parse_parameters(self, params_text: str) -> List[Dict[str, Any]]:

        params = []

        if not params_text.strip():
            return params

        parts = []
        current = []
        depth = 0

        for char in params_text:

            if char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue

            if char in "({[":
                depth += 1
            elif char in ")}]":
                depth -= 1

            current.append(char)

        if current:
            parts.append("".join(current).strip())

        for param in parts:

            if not param:
                continue

            tokens = param.split()

            if len(tokens) >= 2:

                has_default = "=" in param
                name = tokens[-1]

                if "=" in name:
                    name = name.split("=")[0].strip()

                param_type = " ".join(tokens[:-1])

                params.append({
                    "type": param_type,
                    "name": name,
                    "has_default": has_default
                })

            else:

                params.append({
                    "type": "unknown",
                    "name": param,
                    "has_default": False
                })

        return params

    def extract_namespace(self, full_name: str):

        if "." in full_name:

            parts = full_name.split(".")

            return (
                ".".join(parts[:-1]),
                parts[-1]
            )

        return "thisapp", full_name

    def clean_script(self, script: str) -> str:

        script = script.strip()

        if script.startswith("{") and script.endswith("}"):
            script = script[1:-1].strip()

        return script

    def extract_from_content(
        self,
        content: str
    ) -> List[Dict[str, Any]]:

        functions = []

        for return_type, pattern in self.patterns.items():

            for match in re.finditer(
                pattern,
                content,
                re.DOTALL
            ):

                full_name = match.group(1).strip()
                params_text = match.group(2).strip()
                script = match.group(3).strip()

                namespace, name = self.extract_namespace(
                    full_name
                )

                script = self.clean_script(script)

                functions.append({
                    "name": name,
                    "namespace": namespace,
                    "return_type": return_type,
                    "full_name": full_name,
                    "params_text": params_text,
                    "params": self.parse_parameters(
                        params_text
                    ),
                    "script": script,
                    "script_lines": len(
                        script.splitlines()
                    ),
                    "has_script": bool(script)
                })

        return functions

    def extract_from_file(
        self,
        file_path: Path
    ) -> List[Dict[str, Any]]:

        try:

            content = file_path.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            return self.extract_from_content(content)

        except Exception as error:

            print(
                f"Error reading {file_path}: {error}"
            )

            return []

    def save_to_json(
        self,
        functions: List[Dict[str, Any]],
        output_file: Path
    ):

        try:

            output_file.write_text(
                json.dumps(
                    functions,
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

            print(
                f"Created {output_file.name}"
            )

            print(
                f"Functions: {len(functions)}"
            )

        except Exception as error:

            print(
                f"Error creating JSON: {error}"
            )


def main():

    print("==========================================")
    print("DELUGE FUNCTION EXTRACTOR")
    print("==========================================")

    print(f"Input : {INPUT_FILE}")
    print(f"Output: {OUTPUT_FILE}")

    if not INPUT_FILE.exists():

        print()
        print(
            f"ERROR: {INPUT_FILE.name} was not found."
        )

        raise SystemExit(1)

    extractor = DelugeFunctionExtractor()

    functions = extractor.extract_from_file(
        INPUT_FILE
    )

    if not functions:

        print()
        print(
            "ERROR: No functions were found."
        )

        raise SystemExit(1)

    extractor.save_to_json(
        functions,
        OUTPUT_FILE
    )

    print()
    print("==========================================")
    print("DONE")
    print("==========================================")


if __name__ == "__main__":
    main()
