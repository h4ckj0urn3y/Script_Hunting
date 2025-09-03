import sys
import json
from urllib.parse import urlencode, parse_qs, unquote_plus
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re

# --- Conversion Helper Functions ---

def _flatten_dict_for_form(d, parent_key=''):
    """
    Recursively flattens a nested dictionary to prepare it for form URL encoding.
    Handles nested objects and lists.
    Example: {'user': {'name': 'test'}} -> {'user[name]': 'test'}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}[{k}]" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict_for_form(v, new_key).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(_flatten_dict_for_form(item, f"{new_key}[{i}]").items())
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, v))
    return dict(items)

def _xml_to_dict_recursive(node):
    """
    Recursively converts an XML element and its children into a dictionary.
    Handles simple text, children, and lists of same-tagged children.
    """
    result = {}
    if node.text and node.text.strip():
        # If the node has text and no children, it's a simple value
        if not list(node):
            return node.text.strip()

    for child in node:
        child_data = _xml_to_dict_recursive(child)
        # Sanitize tag name (remove namespace)
        tag = re.sub(r'\{.*\}', '', child.tag)

        if tag in result:
            # If key already exists, convert it to a list
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(child_data)
        else:
            result[tag] = child_data
    return result

def _dict_to_xml_recursive(data, root_element):
    """
    Recursively builds an XML tree from a dictionary.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                for item in value:
                    sub_element = ET.SubElement(root_element, key)
                    _dict_to_xml_recursive(item, sub_element)
            else:
                sub_element = ET.SubElement(root_element, key)
                _dict_to_xml_recursive(value, sub_element)
    else:
        # Convert non-string values to string for XML
        root_element.text = str(data)

# --- Parsers (Input String -> Python Dictionary) ---

def parse_json_to_dict(body: str) -> dict:
    """Parses a JSON string into a dictionary."""
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

def parse_form_to_dict(body: str) -> dict:
    """Parses a form-urlencoded string into a dictionary."""
    # parse_qs returns lists for all values, so we simplify them
    parsed = parse_qs(body)
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}

def parse_xml_to_dict(body: str) -> dict:
    """Parses an XML string into a dictionary."""
    try:
        root = ET.fromstring(body)
        return {re.sub(r'\{.*\}', '', root.tag): _xml_to_dict_recursive(root)}
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML format: {e}")

def parse_plain_to_dict(body: str) -> dict:
    """Wraps plain text in a dictionary."""
    return {"text": body}

# --- Formatters (Python Dictionary -> Output String) ---

def format_dict_to_json(data: dict) -> str:
    """Formats a dictionary into a pretty-printed JSON string."""
    return json.dumps(data, indent=2)

def format_dict_to_form(data: dict) -> str:
    """Formats a dictionary into a form-urlencoded string."""
    if not isinstance(data, dict):
        raise TypeError("Form conversion requires dictionary input.")
    flattened_data = _flatten_dict_for_form(data)
    return urlencode(flattened_data)

def format_dict_to_xml(data: dict) -> str:
    """Formats a dictionary into a pretty-printed XML string."""
    if not isinstance(data, dict) or len(data) != 1:
        raise TypeError("XML conversion requires a dictionary with a single root key.")
    
    root_key = list(data.keys())[0]
    root = ET.Element(root_key)
    _dict_to_xml_recursive(data[root_key], root)
    
    # Pretty-print the XML
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def format_dict_to_plain(data: dict) -> str:
    """
    Extracts plain text from a dictionary.
    If the dictionary has a 'text' key, its value is returned.
    Otherwise, the entire dictionary is returned as a JSON string.
    """
    if isinstance(data, dict) and 'text' in data:
        return str(data['text'])
    return json.dumps(data, indent=2)

# --- Core Logic ---

SUPPORTED_TYPES = {
    "json": ("application/json", parse_json_to_dict, format_dict_to_json),
    "form": ("application/x-www-form-urlencoded", parse_form_to_dict, format_dict_to_form),
    "xml": ("text/xml", parse_xml_to_dict, format_dict_to_xml),
    "plain": ("text/plain", parse_plain_to_dict, format_dict_to_plain),
}

def extract_body_from_request(raw_request: str) -> str:
    """Finds and returns the body from a raw HTTP request string."""
    # Find the end of headers, marked by a double newline
    parts = raw_request.split("\r\n\r\n", 1)
    if len(parts) == 2:
        return parts[1]
    
    # Fallback for LF line endings
    parts_lf = raw_request.split("\n\n", 1)
    if len(parts_lf) == 2:
        return parts_lf[1]
        
    # If no separator is found, assume the whole input is the body
    return raw_request

def convert_body(body: str, source_type: str, target_type: str) -> tuple[str, str]:
    """
    Converts a request body from a source content type to a target one.
    Returns a tuple containing the converted body and the new Content-Type header.
    """
    source_type = source_type.lower().strip()
    target_type = target_type.lower().strip()

    if source_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported source type: '{source_type}'. Supported types are: {', '.join(SUPPORTED_TYPES.keys())}")
    if target_type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported target type: '{target_type}'. Supported types are: {', '.join(SUPPORTED_TYPES.keys())}")

    # Step 1: Parse the source body into a common intermediate format (dict)
    _, parser, _ = SUPPORTED_TYPES[source_type]
    intermediate_dict = parser(body)

    # Step 2: Format the dictionary into the target content type string
    target_header, _, formatter = SUPPORTED_TYPES[target_type]
    converted_body = formatter(intermediate_dict)

    return converted_body, f"Content-Type: {target_header}"

# --- UI/CLI Functions ---

def print_help():
    """Prints the usage instructions for the tool."""
    help_text = """
Content-Type Converter Tool

A versatile tool to convert HTTP request bodies between different content types.

USAGE:
  Interactive Mode:
    python content_type_converter.py

    --> The tool will prompt you to paste a full HTTP request, then ask for
        the source and target content types.

  File Mode:
    python content_type_converter.py <filepath> <source_type> <target_type>

    - <filepath>:      Path to a file containing the raw HTTP request.
    - <source_type>:   The content type of the body in the file.
    - <target_type>:   The content type to convert the body to.

  Help:
    python content_type_converter.py --help
    python content_type_converter.py --helpme

SUPPORTED CONTENT TYPES (use short names):
  - json:  application/json
  - form:  application/x-www-form-urlencoded
  - xml:   application/xml
  - plain: text/plain

EXAMPLE (File Mode):
  python content_type_converter.py request.txt json form
"""
    print(help_text)

def run_interactive_mode():
    """Handles the interactive command-line session."""
    print("--- Content-Type Converter: Interactive Mode ---")
    print("Paste your full HTTP request below. Press Ctrl+D (Linux/Mac) or Ctrl+Z then Enter (Windows) when done.")
    
    try:
        raw_request = sys.stdin.read()
        if not raw_request.strip():
            print("\nNo input received. Exiting.")
            return

        body = extract_body_from_request(raw_request).strip()
        
        if not body:
            print("\nCould not extract a body from the request. Exiting.")
            return
            
        print("\n--- Extracted Body ---")
        print(body)
        print("----------------------")

        source_type = input(f"Enter source content type ({', '.join(SUPPORTED_TYPES.keys())}): ").strip("'\" ")
        target_type = input(f"Enter target content type ({', '.join(SUPPORTED_TYPES.keys())}): ").strip("'\" ")

        converted_body, new_header = convert_body(body, source_type, target_type)
        
        print("\n--- New Content-Type Header ---")
        print(new_header)
        print("-------------------------------")
        
        print("\n--- Converted Body ---")
        print(converted_body)
        print("----------------------")

    except (ValueError, TypeError, KeyError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nOperation cancelled. Exiting.")
        
def run_file_mode(filepath: str, source_type: str, target_type: str):
    """Handles the file-based conversion."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_request = f.read()
        
        body = extract_body_from_request(raw_request).strip()
        
        if not body:
            print("ERROR: Could not extract a body from the request file.", file=sys.stderr)
            return

        converted_body, new_header = convert_body(body, source_type, target_type)
        
        print("--- New Content-Type Header ---")
        print(new_header)
        print("-------------------------------")

        print("\n--- Converted Body ---")
        print(converted_body)
        print("----------------------")

    except FileNotFoundError:
        print(f"ERROR: File not found at '{filepath}'", file=sys.stderr)
    except (ValueError, TypeError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)

def main():
    """Main function to parse arguments and run the appropriate mode."""
    args = sys.argv[1:]

    if not args:
        run_interactive_mode()
    elif len(args) == 1 and args[0].lower() in ('--help', '--helpme'):
        print_help()
    elif len(args) == 3:
        filepath, source, target = args
        run_file_mode(filepath, source, target)
    else:
        print("Invalid arguments. Use --help for usage instructions.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

