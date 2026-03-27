#!/usr/bin/env python3
import json
import argparse
import logging
from pathlib import Path
import jsonschema
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    """Returns the absolute path to the project root directory."""
    return Path(__file__).resolve().parent.parent.parent

EXPECTED_SCHEMA = {
    "type": "object",
    "properties": {
        "thinking_process": {
            "type": "string"
        },
        "projectInfo": {
            "type": "object",
            "properties": {
                "repoName": {"type": "string"},
                "agentsMdSource": {"type": "string"}
            },
            "required": ["repoName", "agentsMdSource"],
            "additionalProperties": False
        },
        "rootNode": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "label": {"type": "string"},
                "type": {"type": "string", "enum": ["root"]},
                "children": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "label": {"type": "string"},
                            "type": {"type": "string", "enum": ["category"]},
                            "count": {"type": "integer"},
                            "children": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "type": {"type": "string", "enum": ["rule"]},
                                        "content": {
                                            "type": "object",
                                            "properties": {
                                                "text": {"type": "string"},
                                                "originalHeader": {"type": "string"}
                                            },
                                            "required": ["text", "originalHeader"],
                                            "additionalProperties": False
                                        },
                                        "metadata": {
                                            "type": "object",
                                            "properties": {
                                                "strength": {"type": "string", "enum": ["MUST", "SHOULD"]},
                                                "format": {"type": "string", "enum": ["ListItem", "Paragraph"]}
                                            },
                                            "required": ["strength", "format"],
                                            "additionalProperties": False
                                        }
                                    },
                                    "required": ["id", "type", "content", "metadata"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["id", "label", "type", "count", "children"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["id", "label", "type", "children"],
            "additionalProperties": False
        }
    },
    "required": ["projectInfo", "rootNode"],
    "additionalProperties": False
}


def validate_json_file(file_path: Path) -> tuple[bool, str]:
    """Validates a JSON file against the formal schema."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"JSON Decode Error: {e}"
    except Exception as e:
        return False, f"File Read Error: {e}"

    try:
        jsonschema.validate(instance=data, schema=EXPECTED_SCHEMA)
        return True, "Valid"
    except jsonschema.exceptions.ValidationError as e:
        # Simplify the error message for readability
        return False, f"Schema Error: {e.message} at path: {' -> '.join([str(p) for p in e.path]) if e.path else 'root'}"


def main():
    parser = argparse.ArgumentParser(description="Validate generated JSON AST files against the expected schema.")
    args = parser.parse_args()

    root_dir = get_project_root()
    trees_dir = root_dir / "dataset" / "json_trees"
    
    if not trees_dir.exists():
        logger.error(f"Error: {trees_dir} does not exist.")
        return

    variants = ['llm', 'parser', 'llm_api', 'llm_forced_output']
    
    overall_stats = {}
    
    print("=" * 60)
    print(" JSON ABSTRACT SYNTAX TREE (AST) SCHEMA VALIDATION REPORT ")
    print("=" * 60)

    for variant in variants:
        variant_dir = trees_dir / variant
        if not variant_dir.exists():
            continue
            
        json_files = list(variant_dir.glob("*.json"))
        total_files = len(json_files)
        
        if total_files == 0:
            continue
            
        print(f"\nEvaluating Variant: [{variant.upper()}] ({total_files} files found)")
        print("-" * 60)
        
        valid_count = 0
        error_details = []
        
        for json_file in json_files:
            is_valid, message = validate_json_file(json_file)
            if is_valid:
                valid_count += 1
            else:
                error_details.append(f"  ✗ {json_file.name}: {message}")
                
        success_rate = (valid_count / total_files) * 100
        
        print(f"Schema Compliance: {valid_count}/{total_files} ({success_rate:.1f}%)")
        
        if error_details:
            print("Errors encountered:")
            for err in error_details:
                print(err)
                
        overall_stats[variant] = {
            'total': total_files,
            'valid': valid_count,
            'rate': success_rate
        }

    print("=" * 60)
    print(" FINAL SUMMARY METRICS ")
    print("=" * 60)
    for v, stats in overall_stats.items():
        print(f"{v.ljust(10).upper()} | Valid: {str(stats['valid']).rjust(3)}/{str(stats['total']).ljust(3)} | Compliance: {stats['rate']:.1f}%")
        
    print("\nNext steps suggested for mitigating validity threats:")
    print("1. Low compliance indicates the generation logic produces structural hallucinations.")
    print("2. 'JSON Decode Error' indicates the model failed to output a parseable JSON block at all.")
    print("3. 'Schema Error' indicates missing expected properties, type mismatches, or uncontrolled taxonomy injection.")

if __name__ == "__main__":
    main()
