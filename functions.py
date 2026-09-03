import re
import json
import os
import sys
from typing import Dict, List, Any


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
            "number": r"number\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "time": r"time\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
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
                param_name = tokens[-1]

                if "=" in param_name:
                    param_name = param_name.split("=")[0].strip()

                param_type = " ".join(tokens[:-1])

                params.append({
                    "type": param_type,
                    "name": param_name,
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
            return ".".join(parts[:-1]), parts[-1]

        return "thisapp", full_name

    def clean_script(self, script: str) -> str:
        script = script.strip()

        if script.startswith("{") and script.endswith("}"):
            script = script[1:-1].strip()

        return script

    def extract_from_content(self, content: str) -> List[Dict[str, Any]]:
        functions = []

        for return_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, content, re.DOTALL):
                full_name = match.group(1).strip()
                params_text = match.group(2).strip()
                script = self.clean_script(match.group(3).strip())

                namespace, function_name = self.extract_namespace(full_name)

                functions.append({
                    "name": function_name,
                    "namespace": namespace,
                    "return_type": return_type,
                    "full_name": full_name,
                    "params_text": params_text,
                    "params": self.parse_parameters(params_text),
                    "script": script,
                    "script_lines": len(script.splitlines()),
                    "has_script": bool(script)
                })

        return functions

    def extract_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()

            return self.extract_from_content(content)

        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
            return []

        except Exception as error:
            print(f"Error processing file: {error}")
            return []

    def save_to_json(
        self,
        functions: List[Dict[str, Any]],
        output_file: str = "functions.json"
    ):
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(functions, file, indent=2, ensure_ascii=False)

        print(f"Successfully created '{output_file}'")
        print(f"Functions saved: {len(functions)}")


def main():
    extractor = DelugeFunctionExtractor()

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        possible_files = [
            "functions.ds",
            "functions.txt",
            "Crown_.txt"
        ]

        input_file = next(
            (file for file in possible_files if os.path.exists(file)),
            None
        )

        if input_file is None:
            source_files = (
                list(Path(".").glob("*.ds")) +
                list(Path(".").glob("*.txt"))
            )

            if source_files:
                input_file = str(source_files[0])
            else:
                print("No .ds or .txt input file found.")
                print("Usage: python functions.py your_file.ds")
                sys.exit(1)

    print(f"Reading: {input_file}")

    functions = extractor.extract_from_file(input_file)

    if not functions:
        print("No functions found.")
        sys.exit(1)

    output_file = "functions.json"

    extractor.save_to_json(functions, output_file)

    print(f"Output file: {output_file}")


if __name__ == "__main__":
    main()
