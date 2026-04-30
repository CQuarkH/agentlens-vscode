#!/usr/bin/env python3
import json
import logging
import glob
from pathlib import Path
import difflib
import argparse

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def load_mapping() -> dict:
    root = get_project_root()
    map_path = root / "cat_lab_mapping.json"
    if not map_path.exists():
        logger.error(f"Cannot find map at {map_path}")
        return {}
    with open(map_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def migrate_json_file(input_path: Path, output_path: Path, label_to_cat: dict):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Check if already migrated
    root_children = data.get("rootNode", {}).get("children", [])
    if not root_children:
        return # Skip empty
        
    # Check if it has type "label" anywhere or if we only have 5 macro categories
    macro_cats = {"General", "Implementation", "Build", "Management", "Quality", "Uncategorized"}
    already_migrated = all(child.get("label") in macro_cats for child in root_children)
    if already_migrated:
        logger.info(f"Skipping {input_path.name}: already migrated.")
        if input_path.resolve() != output_path.resolve():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        return

    # Restructure
    new_children = {}
    valid_labels = list(label_to_cat.keys())
    
    for old_cat in root_children:
        old_cat["type"] = "label" # Rename type
        label_name = old_cat.get("label", "Unknown")
        
        macro_cat_name = label_to_cat.get(label_name)
        
        # If exact match fails, try fuzzy matching LLM grammar typos
        if not macro_cat_name:
            matches = difflib.get_close_matches(label_name, valid_labels, n=1, cutoff=0.6)
            if matches:
                matched_label = matches[0]
                macro_cat_name = label_to_cat[matched_label]
                logger.info(f"    Fuzzy resolved '{label_name}' -> '{matched_label}' ({macro_cat_name})")
            else:
                macro_cat_name = "Uncategorized"
                logger.warning(f"    Failed to categorize '{label_name}'")
        
        if macro_cat_name not in new_children:
            new_children[macro_cat_name] = {
                "id": f"macro_{macro_cat_name.lower().replace(' ', '_')}",
                "label": macro_cat_name,
                "type": "category",
                "count": 0,
                "children": []
            }
            
        new_children[macro_cat_name]["children"].append(old_cat)
        new_children[macro_cat_name]["count"] += old_cat.get("count", 0)
        
    data["rootNode"]["children"] = list(new_children.values())
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        
    logger.info(f"Migrated {input_path.name} -> {output_path.parent.name}/{output_path.name}")

def main():
    parser = argparse.ArgumentParser(description="Migrate AST Schema to V2 Macro-Categories")
    parser.add_argument("input_file", nargs="?", help="Path to the input JSON file")
    parser.add_argument("output_file", nargs="?", help="Path to save the migrated JSON file")
    args = parser.parse_args()

    mapping = load_mapping()
    
    # Invert mapping: Label -> Category
    label_to_cat = {}
    for macro_cat, labels in mapping.items():
        for label in labels:
            label_to_cat[label] = macro_cat

    # Si pasamos argumentos, ejecutamos en modo "1 a 1"
    if args.input_file and args.output_file:
        in_p = Path(args.input_file)
        out_p = Path(args.output_file)
        if in_p.exists():
            migrate_json_file(in_p, out_p, label_to_cat)
        else:
            logger.error(f"El archivo de entrada no existe: {in_p}")
        return

    # Fallback (legacy): Iterar todos los JSON si no se pasan argumentos
    root = get_project_root()
    search_path = root / "dataset" / "json_trees" / "**" / "*.json"
    files = glob.glob(str(search_path), recursive=True)
    count = 0
    for f in files:
        if "cat_lab_mapping" in f: continue
        p = Path(f)
        migrate_json_file(p, p, label_to_cat)
        count += 1
        
    logger.info(f"Migration complete! Processed {count} JSON files.")

if __name__ == "__main__":
    main()