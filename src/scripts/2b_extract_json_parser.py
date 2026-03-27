#!/usr/bin/env python3
import json
import argparse
import logging
from pathlib import Path
import subprocess
import re
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

CATEGORY_DEFINITIONS = {
    "System Overview": "Provides a general overview or describes the key features of the system.",
    "AI Integration": "Contains specific instructions on the desired behavior and roles of agentic coding, as well as methods for integrating other AI tools.",
    "Documentation": "Lists supplementary documents, links, or references for additional context.",
    "Architecture": "Describes the high-level structure, design principles, or key components of the system's architecture.",
    "Impl. Details": "Provides specific details for implementing code or system components, including coding style guidelines.",
    "Build and Run": "Outlines the process for compiling source code and running the application, often including key commands.",
    "Testing": "Details the procedures and commands for executing automated tests.",
    "Conf.&Env.": "Instructions for configuring the system and setting up the development or production environment.",
    "DevOps": "Covers procedures for software deployment, release, and operations, such as CI/CD pipelines.",
    "Development Process": "Defines the development workflow, including guidelines for version control systems like Git.",
    "Project Management": "Information related to the planning, organization, and management of the project.",
    "Maintenance": "Guidelines for system maintenance, including strategies for improving readability, detecting and resolving bugs.",
    "Debugging": "Explains error handling techniques and methods for identifying and resolving issues.",
    "Performance": "Focuses on system performance, quality assurance, and potential optimizations.",
    "Security": "Addresses security considerations, vulnerabilities, or best practices for the system.",
    "UI/UX": "Contains guidelines or details concerning the user interface (UI) and user experience (UX)."
}

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def extract_frontmatter_and_content(file_path: Path):
    text = file_path.read_text(encoding='utf-8')
    lines = text.splitlines()
    
    if len(lines) > 0 and lines[0] == '---':
        try:
            end_index = lines.index('---', 1)
            frontmatter_lines = lines[1:end_index]
            content = '\n'.join(lines[end_index+1:])
            
            repo_name = ""
            categories = []
            
            for line in frontmatter_lines:
                if line.startswith('repo:'):
                    repo_name = line.replace('repo:', '').strip().strip('"').strip("'")
                elif line.startswith('categories:'):
                    cat_str = line.replace('categories:', '').strip()
                    if cat_str.startswith('[') and cat_str.endswith(']'):
                        try:
                            categories = json.loads(cat_str)
                        except:
                            pass
                            
            return repo_name, categories, content
        except ValueError:
            pass
            
    return file_path.stem, [], text

def pandoc_markdown_to_ast(markdown_text: str) -> dict:
    try:
        result = subprocess.run(
            ['pandoc', '-f', 'markdown', '-t', 'json'],
            input=markdown_text,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Pandoc execution failed: {e.stderr}")
        return {}
    except Exception as e:
        logger.error(f"Error calling Pandoc: {e}")
        return {}

def extract_all_text_from_node(node) -> str:
    """Recursively extract raw text from any Pandoc AST node with proper spacing."""
    def get_strs(n):
        if isinstance(n, dict):
            t = n.get("t")
            if t == "Str":
                yield n.get("c", "")
            elif t in ["Space", "SoftBreak"]:
                yield " "
            elif t == "LineBreak":
                yield "\n"
            elif t == "Code":
                yield f"`{n.get('c', ['', ''])[1]}`"
            elif t == "CodeBlock":
                yield f"\n```\n{n.get('c', ['', ''])[1]}\n```\n"
            elif t == "Quoted":
                quote_type = n.get("c", [])[0]
                q_char = "'" if (isinstance(quote_type, dict) and quote_type.get("t") == "SingleQuote") else '"'
                yield q_char
                yield from get_strs(n.get("c", [])[1])
                yield q_char
            elif t == "Link":
                yield from get_strs(n.get("c", [])[1])
            elif t in ["Para", "Plain", "Header", "Cell", "Row", "BlockQuote"]:
                yield " "
                yield from get_strs(n.get("c"))
                yield " "
            else:
                yield from get_strs(n.get("c"))
        elif isinstance(n, list):
            for item in n:
                yield from get_strs(item)
                
    text = "".join(list(get_strs(node)))
    return re.sub(r'[ \t]+', ' ', text).strip()

def determine_strength(text: str) -> str:
    must_pattern = r'\b(must|always|never|required|strictly|do not|don\'t)\b'
    if re.search(must_pattern, text, re.IGNORECASE):
        return "MUST"
    return "SHOULD"

def determine_category(text: str, header: str, repo_categories: List[str]) -> str:
    combined_text = (text + " " + header).lower()
    
    # Heuristic 1: Match against repo predefined categories
    for cat in repo_categories:
        if cat.lower() in combined_text:
            return cat
            
    # Heuristic 2: Dictionary keyword matching
    for cat, desc in CATEGORY_DEFINITIONS.items():
        if cat.lower() in combined_text:
            return cat
            
    # Fallback
    if len(repo_categories) > 0:
        return repo_categories[0]
    return "Impl. Details"

def safe_id(string: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', string).strip('_').lower()

def main():
    parser = argparse.ArgumentParser(description="Extract structured JSON from Markdown using Pandoc AST parser.")
    parser.add_argument("-l", "--limit", type=int, help="Limit the number of files to process", default=None)
    args = parser.parse_args()

    root_dir = get_project_root()
    input_dir = root_dir / "dataset" / "enriched_agents"
    output_dir = root_dir / "dataset" / "json_trees" / "parser"
    
    if not input_dir.exists():
        logger.error(f"Input directory {input_dir} does not exist.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    
    processed_count = 0
    md_files = list(input_dir.glob("*.md"))
    if args.limit:
        md_files = md_files[:args.limit]
        
    for md_file in md_files:
        logger.info(f"Processing {md_file.name} via Parser...")
        repo_name, categories, content = extract_frontmatter_and_content(md_file)
        
        ast = pandoc_markdown_to_ast(content)
        if not ast:
            continue
            
        blocks = ast.get("blocks", [])
        
        current_header = "General Context"
        extracted_rules = [] # Tuple of (text, header, format)
        
        # Ast Traversal
        for block in blocks:
            t = block.get("t")
            if t == "Header":
                # c = [level, attr, inlines]
                current_header = extract_all_text_from_node(block.get("c", [])[2])
            elif t in ["Para", "BlockQuote"]:
                text = extract_all_text_from_node(block)
                if text and len(text) > 20: # Ignore very short paragraphs
                    extracted_rules.append((text, current_header, "Paragraph"))
            elif t == "Table":
                table_text = extract_all_text_from_node(block)
                if table_text and len(table_text) > 20:
                    extracted_rules.append((table_text, current_header, "Paragraph"))
            elif t == "BulletList" or t == "OrderedList":
                # c is either [list_items] for BulletList, or [listAttributes, list_items] for OrderedList
                items = block.get("c", [])
                if t == "OrderedList":
                    items = items[1]
                
                for item_blocks in items:
                    # item_blocks is a list of blocks for that list item
                    item_text = " ".join([extract_all_text_from_node(b) for b in item_blocks if extract_all_text_from_node(b)])
                    if item_text:
                        extracted_rules.append((item_text, current_header, "ListItem"))
        
        # Group by category
        categories_map: Dict[str, List[Dict[str, Any]]] = {}
        rule_counter = 1
        
        for text, header, fmt in extracted_rules:
            cat = determine_category(text, header, categories)
            strength = determine_strength(text)
            
            if cat not in categories_map:
                categories_map[cat] = []
                
            categories_map[cat].append({
                "id": f"rule_{rule_counter}",
                "type": "rule",
                "content": {
                    "text": text,
                    "originalHeader": header
                },
                "metadata": {
                    "strength": strength,
                    "format": fmt
                }
            })
            rule_counter += 1
            
        # Build Final JSON AST
        children_nodes = []
        for cat_name, rules in categories_map.items():
            children_nodes.append({
                "id": f"cat_{safe_id(cat_name)}",
                "label": cat_name,
                "type": "category",
                "count": len(rules),
                "children": rules
            })
            
        final_json = {
            "projectInfo": {
                "repoName": repo_name,
                "agentsMdSource": md_file.name
            },
            "rootNode": {
                "id": "root",
                "label": "AGENTS.md Context",
                "type": "root",
                "children": children_nodes
            }
        }
        
        output_file_path = output_dir / md_file.with_suffix('.json').name
        try:
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(final_json, f, indent=2, ensure_ascii=False)
            processed_count += 1
        except Exception as e:
            logger.error(f"Failed to write JSON for {md_file.name}: {e}")

    logger.info(f"Phase 2B (Parser) completed. {processed_count} files processed.")

if __name__ == "__main__":
    main()
