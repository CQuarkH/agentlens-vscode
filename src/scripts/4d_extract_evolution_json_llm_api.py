#!/usr/bin/env python3
import json
import logging
import os
import requests
from pathlib import Path
from anthropic import Anthropic

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CATEGORY_DEFINITIONS = {
    # (Se mantienen exactamente las mismas de tu código original)
    "System Overview": "Provides a general overview or describes the key features of the system.",
    "AI Integration": "Contains specific instructions on the desired behavior and roles of agentic coding...",
    "Documentation": "Lists supplementary documents, links, or references for additional context.",
    "Architecture": "Describes the high-level structure, design principles, or key components...",
    "Impl. Details": "Provides specific details for implementing code or system components...",
    "Build and Run": "Outlines the process for compiling source code and running the application...",
    "Testing": "Details the procedures and commands for executing automated tests.",
    "Conf.&Env.": "Instructions for configuring the system and setting up the environment.",
    "DevOps": "Covers procedures for software deployment, release, and operations...",
    "Development Process": "Defines the development workflow, including guidelines for VCS...",
    "Project Management": "Information related to the planning, organization, and management...",
    "Maintenance": "Guidelines for system maintenance, improving readability, detecting bugs.",
    "Debugging": "Explains error handling techniques and methods for identifying issues.",
    "Performance": "Focuses on system performance, quality assurance, and optimizations.",
    "Security": "Addresses security considerations, vulnerabilities, or best practices...",
    "UI/UX": "Contains guidelines or details concerning the user interface (UI)..."
}

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable is missing.")
        return

    root_dir = get_project_root()
    history_file = root_dir / "dataset" / "evolution_exp" / "file_history.json"
    base_output_dir = root_dir / "dataset" / "evolution_exp" / "json_trees" / "llm_api"
    
    if not history_file.exists():
        logger.error(f"Archivo de historial {history_file} no existe. Ejecuta el Script 4a primero.")
        return

    with open(history_file, 'r', encoding='utf-8') as f:
        history_data = json.load(f)

    client = Anthropic(api_key=api_key)
    logger.info("Initialized Anthropic client.")

    system_prompt = f"""
You are a Lead Data Engineer and expert Information Extractor.
Your task is to extract instructions/rules from the provided markdown document and map them into a strictly defined JSON AST format.

CRITICAL EXTRACTION RULES:
1. EXACT MATCH: The extracted 'text' for each rule MUST be an absolutely identical, verbatim substring of the original markdown content provided. DO NOT normalize characters, DO NOT rephrase, DO NOT change formatting, indentation, or capitalization. Stay 100% faithful to the source text.
2. LINE CITATIONS: For each rule, you must find and cite the exact 1-indexed start and end lines of the rule in the markdown document, outputting them in the metadata as 'line_start' and 'line_end'.

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
            "content": {{ "text": "<Instrucción exacta e identica al markdown>", "originalHeader": "<Contexto H2/H3>" }},
            "metadata": {{ "strength": "<MUST|SHOULD>", "format": "<ListItem|Paragraph>", "line_start": <inicio_linea>, "line_end": <fin_linea> }}
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

    for repo_key, data in history_data.items():
        repo_name_clean = repo_key.replace("/", "_")
        repo_output_dir = base_output_dir / repo_name_clean
        repo_output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"--- Procesando evolución de: {repo_key} ---")
        
        for commit in reversed(data['commits']):
            sha = commit['sha']
            output_file_path = repo_output_dir / f"{sha}.json"
            
            # Si el archivo ya existe, lo saltamos (ahorro en caso de fallo)
            if output_file_path.exists():
                logger.info(f"Saltando {sha[:7]} (Ya procesado)")
                continue
                
            # Descargar contenido raw del markdown en ese commit
            logger.info(f"Descargando raw markdown para commit {sha[:7]}...")
            raw_response = requests.get(commit['raw_url'])
            if raw_response.status_code != 200:
                logger.error(f"Fallo al descargar {commit['raw_url']}")
                continue
                
            content = raw_response.text
            
            user_prompt = f"""
Repository Name: {repo_key}
Commit SHA: {sha}
Source File Name: {data['filePath']}

Document Content:
{content}

Extract the rules based on the instructions above and return the required JSON schema.
"""
            logger.info(f"Generando AST vía LLM para {sha[:7]}...")
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6", # <- Mantenido tal cual el de tu script original
                    max_tokens=16000,
                    temperature=0.0,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                output_text = response.content[0].text.strip()
                
                # Limpiar backticks de markdown si el LLM los pone
                if output_text.startswith("```json"): output_text = output_text[7:]
                if output_text.startswith("```"): output_text = output_text[3:]
                if output_text.endswith("```"): output_text = output_text[:-3]
                output_text = output_text.strip()
                
                parsed_json = json.loads(output_text)
                
                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(parsed_json, f, indent=2, ensure_ascii=False)
                    
                logger.info(f"Guardado exitosamente: {output_file_path.name}")
                processed_count += 1
                
            except json.JSONDecodeError as e:
                logger.error(f"Fallo decodificando JSON para {sha}: {e}")
            except Exception as e:
                logger.error(f"Error procesando {sha}: {e}")

    logger.info(f"Fase 4 (Extracción Histórica) completada. {processed_count} ASTs generados.")

if __name__ == "__main__":
    main()