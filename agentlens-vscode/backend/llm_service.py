import json
import os
import logging

logger = logging.getLogger(__name__)

LLM_CATEGORIES = {
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


def extract_ast_with_llm(file_path: str) -> dict | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable is missing.")
        return None

    from pathlib import Path
    md_path = Path(file_path)
    if not md_path.exists():
        logger.error(f"File not found: {file_path}")
        return None

    md_content = md_path.read_text(encoding="utf-8")
    file_name = md_path.name
    repo_name = md_path.resolve().parent.name

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    system_prompt = f"""
You are a Lead Data Engineer and expert Information Extractor.
Your task is to extract instructions/rules from the provided markdown document and map them into a strictly defined JSON AST format.

CRITICAL EXTRACTION RULES:
1. EXACT MATCH: The extracted 'text' for each rule MUST be an absolutely identical, verbatim substring of the original markdown content provided.
2. LINE CITATIONS: For each rule, you must find and cite the exact 1-indexed start and end lines of the rule.

Here are the system categories available:
{json.dumps(LLM_CATEGORIES, indent=2)}

You MUST output ONLY raw valid JSON. No markdown ticks, no preamble, no trailing text.
You MUST follow this exact schema for the output:
{{
  "projectInfo": {{ "repoName": "<nombre>", "agentsMdSource": "<archivo_origen>" }},
  "rootNode": {{
    "id": "root", "label": "AGENTS.md Context", "type": "root",
    "children": [
      {{
        "id": "cat_<nombre_seguro>", "label": "<Nombre Categoría>", "type": "category", "count": <num_reglas>,
        "children": [
          {{
            "id": "rule_<num>", "type": "rule",
            "content": {{ "text": "<Instrucción exacta>", "originalHeader": "<Contexto H2/H3>" }},
            "metadata": {{ "strength": "<MUST|SHOULD>", "format": "<ListItem|Paragraph>", "line_start": <inicio>, "line_end": <fin> }}
          }}
        ]
      }}
    ]
  }}
}}

For "strength", use "MUST" for strict rules/commands and "SHOULD" for recommendations.
For "format", use "ListItem" if the instruction was a bullet point, or "Paragraph" otherwise.
"""

    user_prompt = f"""
Repository Name: {repo_name}
Source File Name: {file_name}

Document Content:
{md_content}

Extract the rules based on the instructions above and return the required JSON schema.
"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16000,
            temperature=0.0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        output_text = response.content[0].text.strip()

        if output_text.startswith("```json"):
            output_text = output_text[7:]
        if output_text.startswith("```"):
            output_text = output_text[3:]
        if output_text.endswith("```"):
            output_text = output_text[:-3]

        output_text = output_text.strip()
        parsed_json = json.loads(output_text)
        return parsed_json

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return None


def migrate_ast_schema(raw_json: dict) -> dict:
    from pathlib import Path
    import difflib

    cat_lab_mapping_path = Path(__file__).resolve().parent.parent.parent.parent / "cat_lab_mapping.json"
    if cat_lab_mapping_path.exists():
        mapping = json.loads(cat_lab_mapping_path.read_text(encoding="utf-8"))
    else:
        mapping = {
            "General": ["System Overview", "AI Integration", "Documentation"],
            "Implementation": ["Architecture", "Implementation Details"],
            "Build": ["Build & Run", "Testing", "Configuration & Environment", "Conf.&Env.", "DevOps"],
            "Management": ["Development Process", "Project Management"],
            "Quality": ["Maintainability", "Maintenance", "Debugging", "Performance", "Security", "UI/UX"]
        }

    label_to_cat = {}
    for macro_cat, labels in mapping.items():
        for label in labels:
            label_to_cat[label] = macro_cat

    root_children = raw_json.get("rootNode", {}).get("children", [])
    if not root_children:
        return raw_json

    macro_cats = {"General", "Implementation", "Build", "Management", "Quality", "Uncategorized"}
    already_migrated = all(child.get("label") in macro_cats for child in root_children)
    if already_migrated:
        return raw_json

    new_children = {}
    valid_labels = list(label_to_cat.keys())

    for old_cat in root_children:
        old_cat["type"] = "label"
        label_name = old_cat.get("label", "Unknown")

        macro_cat_name = label_to_cat.get(label_name)

        if not macro_cat_name:
            matches = difflib.get_close_matches(label_name, valid_labels, n=1, cutoff=0.6)
            if matches:
                macro_cat_name = label_to_cat[matches[0]]
            else:
                macro_cat_name = "Uncategorized"

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

    raw_json["rootNode"]["children"] = list(new_children.values())
    return raw_json


def extract_frontmatter_and_content(file_path: str):
    from pathlib import Path
    text = Path(file_path).read_text(encoding="utf-8")
    lines = text.splitlines()

    if len(lines) > 0 and lines[0] == '---':
        try:
            end_index = lines.index('---', 1)
            frontmatter_lines = lines[1:end_index]
            content = '\n'.join(lines[end_index + 1:])
            repo_name = ""
            for line in frontmatter_lines:
                if line.startswith('repo:'):
                    repo_name = line.replace('repo:', '').strip().strip('"').strip("'")
            return repo_name, content
        except ValueError:
            pass
    repo_name = Path(file_path).stem
    return repo_name, text
