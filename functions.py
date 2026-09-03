import re
import json
import os
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

class DelugeFunctionExtractor:
    """Extract functions from Deluge (Zoho Creator) files."""
    
    def __init__(self):
        self.functions = []
        self.current_namespace = 'thisapp'
        
        # Patterns for different function signatures
        self.patterns = {
            'void': r'void\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'map': r'map\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'string': r'string\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'int': r'int\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'float': r'float\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'boolean': r'boolean\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'list': r'list\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'date': r'date\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'datetime': r'datetime\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'number': r'number\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
            'time': r'time\s+([.\w]+)\s*\(([^)]*)\)\s*\{([\s\S]*?)\n\s*\}',
        }
    
    def parse_parameters(self, params_text: str) -> List[Dict[str, str]]:
        """Parse function parameters into structured format."""
        params = []
        if not params_text or params_text.strip() == '':
            return params
        
        # Handle nested types
        param_parts = []
        current_param = []
        depth = 0
        
        for char in params_text:
            if char == ',' and depth == 0:
                param_parts.append(''.join(current_param).strip())
                current_param = []
            else:
                if char in '({[':
                    depth += 1
                elif char in ')}]':
                    depth -= 1
                current_param.append(char)
        
        if current_param:
            param_parts.append(''.join(current_param).strip())
        
        for param in param_parts:
            if param:
                # Try to extract type and name
                parts = param.split()
                if len(parts) >= 2:
                    has_default = '=' in param
                    
                    type_parts = parts[:-1]
                    param_name = parts[-1]
                    
                    if '=' in param_name:
                        param_name = param_name.split('=')[0].strip()
                    
                    if len(type_parts) == 1:
                        param_type = type_parts[0]
                    else:
                        param_type = ' '.join(type_parts)
                    
                    params.append({
                        'type': param_type,
                        'name': param_name,
                        'has_default': has_default
                    })
                else:
                    params.append({
                        'type': 'unknown',
                        'name': param,
                        'has_default': False
                    })
        
        return params
    
    def extract_namespace(self, full_name: str) -> tuple:
        """Extract namespace and function name from full name."""
        if '.' in full_name:
            parts = full_name.split('.')
            namespace = '.'.join(parts[:-1])
            func_name = parts[-1]
            return namespace, func_name
        return 'thisapp', full_name
    
    def clean_script(self, script: str) -> str:
        """Clean and format the script body."""
        script = script.strip()
        if script.startswith('{') and script.endswith('}'):
            script = script[1:-1].strip()
        return script
    
    def extract_from_content(self, content: str) -> List[Dict[str, Any]]:
        """Extract all functions from the content."""
        all_functions = []
        
        for return_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                full_name = match.group(1).strip()
                params_text = match.group(2).strip()
                script_body = match.group(3).strip()
                
                namespace, func_name = self.extract_namespace(full_name)
                params = self.parse_parameters(params_text)
                script = self.clean_script(script_body)
                
                func_obj = {
                    'name': func_name,
                    'namespace': namespace,
                    'return_type': return_type,
                    'full_name': full_name,
                    'params_text': params_text,
                    'params': params,
                    'script': script,
                    'script_lines': len(script.split('\n')),
                    'has_script': bool(script)
                }
                
                all_functions.append(func_obj)
        
        return all_functions
    
    def extract_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Extract functions from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find the functions section
            functions_start = content.find('functions')
            if functions_start == -1:
                print("Warning: No 'functions' section found in file. Searching entire file...")
                return self.extract_from_content(content)
            
            # Extract the functions section content
            brace_count = 0
            functions_end = functions_start
            for i, char in enumerate(content[functions_start:], start=functions_start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        functions_end = i + 1
                        break
            
            functions_content = content[functions_start:functions_end]
            
            # Extract functions from the functions section
            functions = self.extract_from_content(functions_content)
            
            # Also search the rest of the file for standalone functions
            rest_content = content[:functions_start] + content[functions_end:]
            standalone_functions = self.extract_from_content(rest_content)
            
            # Merge and deduplicate
            all_functions = functions.copy()
            existing_names = {f['full_name'] for f in functions}
            
            for func in standalone_functions:
                if func['full_name'] not in existing_names:
                    all_functions.append(func)
                    existing_names.add(func['full_name'])
            
            return all_functions
            
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.")
            return []
        except Exception as e:
            print(f"Error processing file: {e}")
            return []
    
    def save_to_json(self, functions: List[Dict[str, Any]], output_file: str, include_script: bool = True) -> None:
        """Save functions to a JSON file."""
        data = []
        
        for func in functions:
            func_data = {
                'name': func['name'],
                'namespace': func['namespace'],
                'return_type': func['return_type'],
                'full_name': func['full_name'],
                'params_text': func['params_text'],
                'params': func['params'],
                'script_lines': func['script_lines']
            }
            
            if include_script:
                func_data['script'] = func['script']
            
            data.append(func_data)
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Successfully saved {len(data)} functions to {output_file}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")
    
    def print_summary(self, functions: List[Dict[str, Any]]) -> None:
        """Print a summary of extracted functions."""
        if not functions:
            print("No functions found.")
            return
        
        print("\n" + "=" * 70)
        print("FUNCTIONS EXTRACTION SUMMARY")
        print("=" * 70)
        print(f"Total functions found: {len(functions)}")
        
        # Group by namespace
        namespace_count = {}
        return_type_count = {}
        
        for func in functions:
            ns = func['namespace']
            namespace_count[ns] = namespace_count.get(ns, 0) + 1
            rt = func['return_type']
            return_type_count[rt] = return_type_count.get(rt, 0) + 1
        
        print("\n" + "-" * 40)
        print("By Namespace:")
        for ns, count in sorted(namespace_count.items()):
            print(f"  {ns}: {count}")
        
        print("\n" + "-" * 40)
        print("By Return Type:")
        for rt, count in sorted(return_type_count.items()):
            print(f"  {rt}: {count}")
        
        print("\n" + "-" * 40)
        print("Function List (First 20):")
        for i, func in enumerate(functions[:20]):
            params_display = func['params_text'] if func['params_text'] else ''
            print(f"  {i+1:2d}. {func['return_type']} {func['full_name']}({params_display})")
        
        if len(functions) > 20:
            print(f"  ... and {len(functions) - 20} more")
        
        print("=" * 70)


def get_input_file():
    """Get input file path from command line or interactive input."""
    # Check command line arguments
    if len(sys.argv) > 1:
        return sys.argv[1]
    
    # Check if running in non-interactive environment
    if not sys.stdin.isatty():
        # Try environment variable
        file_path = os.environ.get('INPUT_FILE', 'fields.ds')
        print(f"Using INPUT_FILE environment variable: {file_path}")
        return file_path
    
    # Interactive mode
    default_file = 'fields.ds'
    try:
        file_path = input(f"Enter the Deluge file path (default: {default_file}): ").strip()
        return file_path if file_path else default_file
    except (EOFError, KeyboardInterrupt):
        print(f"\nUsing default file: {default_file}")
        return default_file


def get_output_file():
    """Get output file path from command line or interactive input."""
    # Check command line arguments
    if len(sys.argv) > 2:
        return sys.argv[2]
    
    # Check environment variable
    output_file = os.environ.get('OUTPUT_FILE', 'functions.json')
    
    # If in interactive mode, ask user
    if sys.stdin.isatty():
        try:
            default_output = output_file
            response = input(f"Enter output JSON file path (default: {default_output}): ").strip()
            if response:
                output_file = response
        except (EOFError, KeyboardInterrupt):
            print(f"\nUsing default output: {output_file}")
    
    return output_file


def get_include_script():
    """Get include_script flag from command line or interactive input."""
    # Check command line arguments
    if len(sys.argv) > 3:
        return sys.argv[3].lower() != 'false'
    
    # Check environment variable
    include_script_env = os.environ.get('INCLUDE_SCRIPT', 'true')
    if include_script_env.lower() == 'false':
        return False
    
    # If in interactive mode, ask user
    if sys.stdin.isatty():
        try:
            response = input("Include script body in JSON? (y/n, default: y): ").strip().lower()
            if response == 'n':
                return False
        except (EOFError, KeyboardInterrupt):
            print("\nIncluding script body by default.")
    
    return True


def main():
    """Main function to run the extractor."""
    extractor = DelugeFunctionExtractor()
    
    # Get input file
    input_file = get_input_file()
    print(f"Input file: {input_file}")
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        # Try alternative paths
        if input_file == 'fields.ds' and os.path.exists('fields.txt'):
            input_file = 'fields.txt'
            print(f"Found fields.txt, using that instead.")
        elif input_file == 'fields.ds' and os.path.exists('Crown_.txt'):
            input_file = 'Crown_.txt'
            print(f"Found Crown_.txt, using that instead.")
        else:
            # Try to find any .ds or .txt file
            ds_files = list(Path('.').glob('*.ds')) + list(Path('.').glob('*.txt'))
            if ds_files:
                input_file = str(ds_files[0])
                print(f"Found {input_file}, using that instead.")
            else:
                print("No suitable input file found.")
                sys.exit(1)
    
    # Extract functions
    print(f"\nExtracting functions from '{input_file}'...")
    functions = extractor.extract_from_file(input_file)
    
    if not functions:
        print("No functions found in the file.")
        sys.exit(0)
    
    # Get output file
    output_file = get_output_file()
    print(f"Output file: {output_file}")
    
    # Get include_script flag
    include_script = get_include_script()
    print(f"Include script: {include_script}")
    
    # Save to JSON
    extractor.save_to_json(functions, output_file, include_script)
    
    # Print summary
    extractor.print_summary(functions)
    
    # Show sample function
    if functions:
        print("\n" + "=" * 70)
        print("SAMPLE FUNCTION (First extracted)")
        print("=" * 70)
        sample = functions[0]
        print(f"Name: {sample['name']}")
        print(f"Namespace: {sample['namespace']}")
        print(f"Return Type: {sample['return_type']}")
        print(f"Full Name: {sample['full_name']}")
        print(f"Params: {sample['params_text']}")
        print(f"Script Lines: {sample['script_lines']}")
        if include_script:
            print("\nScript Preview:")
            script_preview = sample['script'][:300] + "..." if len(sample['script']) > 300 else sample['script']
            print(script_preview)


if __name__ == "__main__":
    main()
