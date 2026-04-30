#!/usr/bin/env python3
import json
import logging
import os
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TARGETS = [
    {"owner": "cartography-cncf", "repo": "cartography", "path": "AGENTS.md"},
    {"owner": "deeeed", "repo": "audiolab", "path": "CLAUDE.md"}
]

WINDOW_SIZE = 10

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

def fetch_all_file_commits(owner, repo, path, token):
    """Obtiene la lista completa de todos los commits de un archivo."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    
    commits = []
    page = 1
    
    logger.info(f"Consultando historial completo de {owner}/{repo}/{path}...")
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"path": path, "per_page": 100, "page": page}
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            logger.error(f"Error GitHub API ({response.status_code}): {response.text}")
            break
            
        data = response.json()
        if not data:
            break
            
        commits.extend(data)
        if len(data) < 100:
            break
        page += 1
        
    return commits

def get_commit_file_stats(owner, repo, commit_sha, path, token):
    """Obtiene el numero de cambios (additions + deletions) de un archivo en un commit."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
        
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        for file in data.get('files', []):
            if file.get('filename') == path:
                return file.get('changes', 0)
    return 0

def main():
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        logger.warning("GITHUB_TOKEN no está configurado. Podrías alcanzar el límite de la API de GitHub.")

    root_dir = get_project_root()
    output_dir = root_dir / "dataset" / "evolution_exp"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "file_history.json"
    history_data = {}

    for target in TARGETS:
        owner = target["owner"]
        repo = target["repo"]
        path = target["path"]
        repo_key = f"{owner}/{repo}"
        
        # 1. Obtener todos los commits
        all_commits_raw = fetch_all_file_commits(owner, repo, path, github_token)
        logger.info(f"Se encontraron {len(all_commits_raw)} commits en total para {repo_key}.")
        
        if not all_commits_raw:
            continue

        # 2. Obtener estadísticas de cada commit
        commits_with_stats = []
        logger.info(f"Analizando estadísticas de cambios para cada commit...")
        
        for c in all_commits_raw:
            sha = c['sha']
            changes = get_commit_file_stats(owner, repo, sha, path, github_token)
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}"
            
            commits_with_stats.append({
                "sha": sha,
                "date": c['commit']['author']['date'],
                "message": c['commit']['message'].split('\n')[0],
                "changes": changes,
                "raw_url": raw_url
            })

        # 3. Aplicar Sliding Window (Ventana Deslizante) para buscar los 10 seguidos más relevantes
        best_window = []
        max_changes = -1
        
        if len(commits_with_stats) <= WINDOW_SIZE:
            logger.info("El historial tiene 10 commits o menos. Se usarán todos.")
            best_window = commits_with_stats
        else:
            logger.info(f"Buscando la ventana de {WINDOW_SIZE} commits seguidos con más cambios...")
            # GitHub devuelve del más nuevo al más viejo. 
            # Recorremos todas las ventanas posibles de tamaño 10.
            for i in range(len(commits_with_stats) - WINDOW_SIZE + 1):
                window = commits_with_stats[i : i + WINDOW_SIZE]
                window_score = sum(c['changes'] for c in window)
                
                if window_score > max_changes:
                    max_changes = window_score
                    best_window = window
            
            logger.info(f"Mejor ventana encontrada: Suma de cambios = {max_changes}")

        # Mostrar resumen por consola
        logger.info(f"\n--- Commits seleccionados para {repo_key} ---")
        for c in best_window:
            logger.info(f"[{c['sha'][:7]}] Cambios: {c['changes']:3d} | {c['date']} | {c['message']}")
        print("\n")

        history_data[repo_key] = {
            "repoName": repo_key,
            "filePath": path,
            "commits": best_window
        }

    # 4. Guardar resultado
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=2)
        
    logger.info(f"Historial (Ventanas óptimas) guardado exitosamente en: {output_file}")

if __name__ == "__main__":
    main()