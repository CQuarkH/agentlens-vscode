#!/usr/bin/env python3
import json
import argparse
import logging
from pathlib import Path
import os
from anthropic import Anthropic

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

def main():
    parser = argparse.ArgumentParser(description="Extract structured JSON from Markdown using Anthropic API.")
    parser.add_argument("-l", "--limit", type=int, help="Limit the number of files to process", default=None)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable is missing. Please set it before running.")
        return

    root_dir = get_project_root()
    input_dir = root_dir / "dataset" / "enriched_agents"
    output_dir = root_dir / "dataset" / "json_trees" / "llm_api"
    
    if not input_dir.exists():
        logger.error(f"Input directory {input_dir} does not exist.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    
    client = Anthropic(api_key=api_key)
    logger.info("Initialized Anthropic client.")

    system_prompt = f"""
You are a Lead Data Engineer and expert Information Extractor.
Your task is to extract instructions/rules from the provided markdown document and map them into a strictly defined JSON AST format.

Here are the system categories available:
{json.dumps(CATEGORY_DEFINITIONS, indent=2)}

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
            "content": {{ "text": "<Instrucción completa>", "originalHeader": "<Contexto H2/H3>" }},
            "metadata": {{ "strength": "<MUST|SHOULD>", "format": "<ListItem|Paragraph>" }}
          }}
        ]
      }}
    ]
  }}
}}

For "strength", use "MUST" for strict rules/commands and "SHOULD" for recommendations.
For "format", use "ListItem" if the instruction was a bullet point, or "Paragraph" otherwise.
"""

    processed_count = 0
    
    md_files = list(input_dir.glob("*.md"))
    if args.limit:
        md_files = md_files[:args.limit]
        
    for md_file in md_files:
        logger.info(f"Processing {md_file.name} via Anthropic API...")
        repo_name, categories, content = extract_frontmatter_and_content(md_file)
        
        user_prompt = f"""
Repository Name: {repo_name}
Source File Name: {md_file.name}
Assigned Categories for this Repo: {json.dumps(categories)}

Document Content:
{content}

Extract the rules based on the instructions above and return the required JSON schema.
"""
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
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
            
            output_file_path = output_dir / md_file.with_suffix('.json').name
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(parsed_json, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Successfully processed and saved JSON for {md_file.name}")
            processed_count += 1
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from API for {md_file.name}: {e}")
            logger.debug(f"Raw Output: {output_text}")
        except Exception as e:
            logger.error(f"An error occurred while processing {md_file.name}: {e}")

    logger.info(f"Phase 2C (Anthropic API) completed. {processed_count} files processed.")

if __name__ == "__main__":
    main()
