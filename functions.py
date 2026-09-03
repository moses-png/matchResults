import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "fields.ds"
OUTPUT_FILE = BASE_DIR / "functions.json"


RETURN_TYPES = [
    "void",
    "map",
    "string",
    "int",
    "float",
    "boolean",
    "list",
    "date",
    "datetime",
    "number",
    "time"
]


class DelugeFunctionExtractor:

    def clean_function(self, function_text: str) -> str:

        function_text = function_text.strip()

        function_text = re.sub(
            r"\r\n?",
            "\n",
            function_text
        )

        return function_text

    def find_matching_brace(
        self,
        text: str,
        opening_brace: int
    ) -> int:

        depth = 0
        in_string = False
        string_char = None
        escaped = False

        for i in range(
            opening_brace,
            len(text)
        ):

            char = text[i]

            if escaped:

                escaped = False
                continue

            if char == "\\" and in_string:

                escaped = True
                continue

            if char in ['"', "'"]:

                if in_string:

                    if char == string_char:
                        in_string = False
                        string_char = None

                else:

                    in_string = True
                    string_char = char

                continue

            if in_string:
                continue

            if char == "{":

                depth += 1

            elif char == "}":

                depth -= 1

                if depth == 0:

                    return i

        return -1

    def extract_functions(
        self,
        content: str
    ):

        functions = []

        pattern = re.compile(
            r"\b("
            + "|".join(RETURN_TYPES)
            + r")\s+"
            r"([A-Za-z_][A-Za-z0-9_.]*)"
            r"\s*\("
        )

        for match in pattern.finditer(content):

            return_type = match.group(1)
            function_name = match.group(2)

            opening_paren = content.find(
                "(",
                match.start()
            )

            if opening_paren == -1:
                continue

            depth = 0
            closing_paren = -1

            for i in range(
                opening_paren,
                len(content)
            ):

                char = content[i]

                if char == "(":
                    depth += 1

                elif char == ")":

                    depth -= 1

                    if depth == 0:

                        closing_paren = i
                        break

            if closing_paren == -1:
                continue

            opening_brace = content.find(
                "{",
                closing_paren
            )

            if opening_brace == -1:
                continue

            between = content[
                closing_paren + 1:
                opening_brace
            ]

            if between.strip():
                continue

            closing_brace = self.find_matching_brace(
                content,
                opening_brace
            )

            if closing_brace == -1:
                continue

            function_text = content[
                match.start():
                closing_brace + 1
            ]

            function_text = self.clean_function(
                function_text
            )

            functions.append({
                "function": function_text
            })

        return self.remove_duplicates(
            functions
        )

    def remove_duplicates(
        self,
        functions
    ):

        result = []
        seen = set()

        for function in functions:

            script = function["function"]

            if script in seen:
                continue

            seen.add(script)

            result.append(function)

        return result

    def extract_from_file(
        self,
        input_file: Path
    ):

        if not input_file.exists():

            raise FileNotFoundError(
                f"Input file not found: "
                f"{input_file}"
            )

        content = input_file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        functions_start = re.search(
            r"\bfunctions\s*\{",
            content,
            re.IGNORECASE
        )

        if not functions_start:

            print(
                "No functions section found."
            )

            return []

        functions_opening_brace = (
            content.find(
                "{",
                functions_start.start()
            )
        )

        functions_closing_brace = (
            self.find_matching_brace(
                content,
                functions_opening_brace
            )
        )

        if functions_closing_brace == -1:

            print(
                "Could not find the end "
                "of the functions section."
            )

            return []

        functions_content = content[
            functions_opening_brace:
            functions_closing_brace + 1
        ]

        return self.extract_functions(
            functions_content
        )

    def save_json(
        self,
        functions,
        output_file: Path
    ):

        with output_file.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                functions,
                file,
                indent=2,
                ensure_ascii=False
            )

    def run(self):

        print("=" * 70)
        print("DELUGE FUNCTION EXTRACTOR")
        print("=" * 70)

        print()
        print(
            f"Input : {INPUT_FILE}"
        )

        print(
            f"Output: {OUTPUT_FILE}"
        )

        print()

        functions = self.extract_from_file(
            INPUT_FILE
        )

        if not functions:

            print(
                "No functions found."
            )

            return

        self.save_json(
            functions,
            OUTPUT_FILE
        )

        print(
            f"Functions found: "
            f"{len(functions)}"
        )

        print(
            f"Created: "
            f"{OUTPUT_FILE}"
        )

        print()
        print("Extraction completed.")


def main():

    extractor = DelugeFunctionExtractor()

    try:

        extractor.run()

    except FileNotFoundError as error:

        print(
            f"ERROR: {error}"
        )

        raise SystemExit(1)

    except Exception as error:

        print(
            f"ERROR: {error}"
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
