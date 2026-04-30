#!/usr/bin/env python3
import json
import logging
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def main():
    root_dir = get_project_root()
    history_file = root_dir / "dataset" / "evolution_exp" / "file_history.json"
    base_cache_dir = root_dir / "dataset" / "evolution_exp" / "agents_cache"
    
    if not history_file.exists():
        logger.error(f"Archivo de historial {history_file} no existe.")
        return

    with open(history_file, 'r', encoding='utf-8') as f:
        history_data = json.load(f)

    downloaded_count = 0

    for repo_key, data in history_data.items():
        repo_name_clean = repo_key.replace("/", "_")
        repo_cache_dir = base_cache_dir / repo_name_clean
        repo_cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"--- Sincronizando Markdown Cache para: {repo_key} ---")
        
        for commit in data['commits']:
            sha = commit['sha']
            output_file_path = repo_cache_dir / f"{sha}.md"
            
            if output_file_path.exists():
                logger.info(f"Saltando {sha[:7]} (Ya existe en caché)")
                continue
                
            logger.info(f"Descargando markdown para commit {sha[:7]}...")
            try:
                raw_response = requests.get(commit['raw_url'], timeout=10)
                if raw_response.status_code == 200:
                    with open(output_file_path, "w", encoding="utf-8") as out_f:
                        out_f.write(raw_response.text)
                    downloaded_count += 1
                else:
                    logger.error(f"Fallo al descargar {commit['raw_url']} (Status: {raw_response.status_code})")
            except Exception as e:
                logger.error(f"Error descargando {sha}: {e}")

    logger.info(f"✅ Caché sincronizado. {downloaded_count} nuevos archivos markdown descargados.")

if __name__ == "__main__":
    main()