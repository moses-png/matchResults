import re
import json
import os
from typing import Dict, List, Any


class DelugeFunctionExtractor:

    def __init__(self):
        self.patterns = {
            "void": r"void\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "map": r"map\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "string": r"string\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "int": r"int\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "float": r"float\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "boolean": r"boolean\s+([.\w]+)\s*\(([^)]*)\s*\{([\s\S]*?)\n\s*\}",
            "list": r"list\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "date": r"date\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "datetime": r"datetime\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "number": r"number\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
            "time": r"time\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}",
        }

    def parse_parameters(self, params_text: str) -> List[Dict[str, Any]]:

        params = []

        if not params_text or not params_text.strip():
            return params

        param_parts = []
        current_param = []
        depth = 0

        for char in params_text:

            if char == "," and depth == 0:
                param_parts.append(
                    "".join(current_param).strip()
                )
                current_param = []
                continue

            if char in "({[":
                depth += 1

            elif char in ")}]":
                depth -= 1

            current_param.append(char)

        if current_param:
            param_parts.append(
                "".join(current_param).strip()
            )

        for param in param_parts:

            if not param:
                continue

            parts = param.split()

            if len(parts) >= 2:

                has_default = "=" in param

                param_name = parts[-1]

                if "=" in param_name:
                    param_name = param_name.split("=")[0].strip()

                param_type = " ".join(parts[:-1])

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

            namespace = ".".join(parts[:-1])
            function_name = parts[-1]

            return namespace, function_name

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

        all_functions = []

        for return_type, pattern in self.patterns.items():

            matches = re.finditer(
                pattern,
                content,
                re.DOTALL
            )

            for match in matches:

                full_name = match.group(1).strip()
                params_text = match.group(2).strip()
                script_body = match.group(3).strip()

                namespace, function_name = (
                    self.extract_namespace(full_name)
                )

                params = self.parse_parameters(
                    params_text
                )

                script = self.clean_script(
                    script_body
                )

                function_data = {
                    "name": function_name,
                    "namespace": namespace,
                    "return_type": return_type,
                    "full_name": full_name,
                    "params_text": params_text,
                    "params": params,
                    "script": script,
                    "script_lines": len(
                        script.split("\n")
                    ),
                    "has_script": bool(script)
                }

                all_functions.append(function_data)

        return all_functions

    def extract_from_file(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as file:

                content = file.read()

            functions_start = content.find(
                "functions"
            )

            if functions_start == -1:

                print(
                    "No 'functions' section found."
                )

                print(
                    "Searching entire file..."
                )

                return self.extract_from_content(
                    content
                )

            brace_count = 0
            functions_end = functions_start

            for i, char in enumerate(
                content[functions_start:],
                start=functions_start
            ):

                if char == "{":
                    brace_count += 1

                elif char == "}":

                    brace_count -= 1

                    if brace_count == 0:

                        functions_end = i + 1
                        break

            functions_content = content[
                functions_start:functions_end
            ]

            functions = self.extract_from_content(
                functions_content
            )

            rest_content = (
                content[:functions_start]
                +
                content[functions_end:]
            )

            standalone_functions = (
                self.extract_from_content(
                    rest_content
                )
            )

            all_functions = functions.copy()

            existing_names = {
                function["full_name"]
                for function in functions
            }

            for function in standalone_functions:

                if function["full_name"] not in existing_names:

                    all_functions.append(
                        function
                    )

                    existing_names.add(
                        function["full_name"]
                    )

            return all_functions

        except FileNotFoundError:

            print(
                f"Error: File '{file_path}' not found."
            )

            return []

        except Exception as error:

            print(
                f"Error processing file: {error}"
            )

            return []

    def save_to_json(
        self,
        functions: List[Dict[str, Any]],
        output_file: str
    ):

        try:

            with open(
                output_file,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    functions,
                    file,
                    indent=2,
                    ensure_ascii=False
                )

            print(
                f"Successfully saved "
                f"{len(functions)} functions "
                f"to {output_file}"
            )

        except Exception as error:

            print(
                f"Error saving JSON: {error}"
            )

    def print_summary(
        self,
        functions: List[Dict[str, Any]]
    ):

        if not functions:

            print("No functions found.")

            return

        print()
        print("=" * 70)
        print("FUNCTIONS EXTRACTION SUMMARY")
        print("=" * 70)

        print(
            f"Total functions found: "
            f"{len(functions)}"
        )

        namespace_count = {}
        return_type_count = {}

        for function in functions:

            namespace = function["namespace"]
            return_type = function["return_type"]

            namespace_count[namespace] = (
                namespace_count.get(namespace, 0) + 1
            )

            return_type_count[return_type] = (
                return_type_count.get(return_type, 0) + 1
            )

        print()
        print("By Namespace:")

        for namespace, count in sorted(
            namespace_count.items()
        ):

            print(
                f"  {namespace}: {count}"
            )

        print()
        print("By Return Type:")

        for return_type, count in sorted(
            return_type_count.items()
        ):

            print(
                f"  {return_type}: {count}"
            )

        print()
        print("Function List:")

        for i, function in enumerate(
            functions,
            start=1
        ):

            params = function["params_text"]

            print(
                f"  {i}. "
                f"{function['return_type']} "
                f"{function['full_name']}"
                f"({params})"
            )

        print("=" * 70)


def main():

    input_file = "fields.ds"
    output_file = "functions.json"

    print("=" * 70)
    print("DELUGE FUNCTION EXTRACTOR")
    print("=" * 70)

    print()
    print(
        f"Input file : {input_file}"
    )

    print(
        f"Output file: {output_file}"
    )

    if not os.path.exists(input_file):

        print()
        print(
            f"ERROR: '{input_file}' "
            f"does not exist."
        )

        print()
        print(
            "Make sure fields.ds is in "
            "the same folder as this Python file."
        )

        return

    extractor = DelugeFunctionExtractor()

    print()
    print(
        f"Extracting functions from "
        f"'{input_file}'..."
    )

    functions = extractor.extract_from_file(
        input_file
    )

    if not functions:

        print()
        print(
            "No functions were found."
        )

        return

    extractor.save_to_json(
        functions,
        output_file
    )

    extractor.print_summary(
        functions
    )

    print()
    print(
        f"Done. '{output_file}' "
        f"has been created."
    )


if __name__ == "__main__":
    main()
