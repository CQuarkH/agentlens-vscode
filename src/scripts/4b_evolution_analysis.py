import os
import re
import yaml
import subprocess
import tempfile
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración de rutas
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATASET_DIR = os.path.join(PROJECT_ROOT, 'dataset')

INPUT_DIR = os.path.join(DATASET_DIR, 'enriched_agents_top_categories')
OUTPUT_DIR = os.path.join(DATASET_DIR, 'evolution_analysis')

def extract_repo_name(file_path):
    """Extrae el nombre del repositorio desde el frontmatter."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if match:
            metadata = yaml.safe_load(match.group(1))
            return metadata.get('repo')
    return None

def analyze_git_history(repo_name):
    """Clona el repo y extrae métricas filtrando por el archivo principal (priorizando la raíz)."""
    repo_url = f"https://github.com/{repo_name}.git"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Clonación 'treeless' (filtra blobs)
        clone_cmd = ["git", "clone", "--filter=blob:none", repo_url, tmpdir]
        subprocess.run(clone_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if not os.path.exists(os.path.join(tmpdir, '.git')):
            return None # Falló el clone (repo privado o no existe)

        ai_files = [
            "agents.md", "claude.md", "copilot.md", 
            "cursor.md", ".cursorrules", ".clauderc", "ai.md"
        ]
        
        pathspecs = []
        for f in ai_files:
            pathspecs.append(f":(icase){f}")       # En la raíz
            pathspecs.append(f":(icase)**/{f}")    # En subcarpetas

        # Agregamos --no-renames para asegurar que la ruta del archivo se lea limpia
        log_cmd = ["git", "log", "--all", "--numstat", "--no-renames", "--format=COMMIT|%H", "--"] + pathspecs
        log_result = subprocess.run(log_cmd, cwd=tmpdir, capture_output=True, text=True)
        
        # Diccionarios para agrupar los datos por cada archivo encontrado
        commits_by_file = {}
        lines_by_file = {}
        
        current_commit = None
        for line in log_result.stdout.split('\n'):
            if line.startswith('COMMIT|'):
                current_commit = line.split('|')[1]
            elif line.strip() and current_commit:
                parts = line.split(maxsplit=2)
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    added = int(parts[0])
                    deleted = int(parts[1])
                    filename = parts[2]
                    
                    if filename not in commits_by_file:
                        commits_by_file[filename] = set()
                        lines_by_file[filename] = {'added': 0, 'deleted': 0}
                        
                    commits_by_file[filename].add(current_commit)
                    lines_by_file[filename]['added'] += added
                    lines_by_file[filename]['deleted'] += deleted

        # Si no se encontró absolutamente nada
        if not commits_by_file:
            return {
                "repo": repo_name, "commits": 0, "lines_added": 0, "lines_deleted": 0,
                "total_lines_changed": 0, "net_lines_growth": 0, "releases_involved": 0,
                "real_files_found": ""
            }

        # Separar archivos: Los que están en la raíz no tienen '/' en la ruta
        root_files = [f for f in commits_by_file.keys() if '/' not in f]
        
        # Lógica de prioridad
        if root_files:
            # Si hay en la raíz, elegimos el que tenga más commits
            principal_file = max(root_files, key=lambda f: len(commits_by_file[f]))
        else:
            # Si no, elegimos el mejor de las subcarpetas
            principal_file = max(commits_by_file.keys(), key=lambda f: len(commits_by_file[f]))

        # Extraemos las métricas SÓLO del archivo ganador
        commit_hashes = commits_by_file[principal_file]
        commits_count = len(commit_hashes)
        lines_added = lines_by_file[principal_file]['added']
        lines_deleted = lines_by_file[principal_file]['deleted']

        # 2. Obtener releases/tags donde SOLO el archivo principal fue modificado
        releases = set()
        for commit in commit_hashes:
            tag_cmd = ["git", "tag", "--contains", commit]
            tag_result = subprocess.run(tag_cmd, cwd=tmpdir, capture_output=True, text=True)
            for tag in tag_result.stdout.split('\n'):
                if tag.strip():
                    releases.add(tag.strip())
                    
        return {
            "repo": repo_name,
            "commits": commits_count,
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "total_lines_changed": lines_added + lines_deleted,
            "net_lines_growth": lines_added - lines_deleted,
            "releases_involved": len(releases),
            "real_files_found": principal_file # Guarda SOLO el nombre ganador
        }

def generate_plots(df):
    """Genera ploteos estadísticos para tomar decisiones sobre qué datos retener."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(10, 6))
    sns.histplot(data=df, x="commits", bins=15, kde=True, color="blue")
    plt.title("Distribución de la cantidad de Commits por archivo")
    plt.xlabel("Cantidad de Commits")
    plt.ylabel("Frecuencia (Cantidad de Archivos)")
    plt.savefig(os.path.join(OUTPUT_DIR, "1_commits_distribution.png"))
    plt.close()

    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x="total_lines_changed", color="lightgreen")
    plt.title("Dispersión de Líneas Totales Modificadas")
    plt.xlabel("Líneas Totales Cambiadas (Agregadas + Borradas)")
    plt.savefig(os.path.join(OUTPUT_DIR, "2_lines_changed_boxplot.png"))
    plt.close()

    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x="commits", y="releases_involved", size="total_lines_changed", sizes=(50, 500), alpha=0.7)
    plt.title("Relación entre Commits, Releases y Volumen de Código cambiado")
    plt.xlabel("Cantidad de Commits")
    plt.ylabel("Cantidad de Releases")
    plt.savefig(os.path.join(OUTPUT_DIR, "3_commits_vs_releases_scatter.png"))
    plt.close()

def main():
    if not os.path.exists(INPUT_DIR):
        print(f"Error: El directorio {INPUT_DIR} no existe. Ejecuta el script 4_a primero.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Iniciando análisis de evolución de archivos (Esto puede tomar unos minutos dependiendo de la red)...")
    
    results = []
    
    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith('.md'):
            continue
            
        file_path = os.path.join(INPUT_DIR, filename)
        repo_name = extract_repo_name(file_path)
        
        if repo_name:
            print(f"Analizando repo: {repo_name}...")
            stats = analyze_git_history(repo_name)
            
            if stats:
                stats['filename'] = filename
                results.append(stats)
                
                # Feedback en consola con el nombre real encontrado
                real_files = stats.get('real_files_found', '')
                if real_files:
                    print(f"  -> OK. Encontrado en git como: {real_files} ({stats['commits']} commits)")
                else:
                    print(f"  -> 0 commits (No se hallaron archivos que matcheen en la historia)")
            else:
                print(f"  -> ERROR. No se pudo obtener el historial para {repo_name} (Clon fallido)")
                
    if not results:
        print("No se extrajeron datos de ningún repositorio.")
        return

    # Convertir a DataFrame de Pandas
    df = pd.DataFrame(results)
    
    # Calcular algunas métricas estadísticas globales
    stats_summary = df.describe()
    print("\n--- RESUMEN ESTADÍSTICO ---")
    print(stats_summary[['commits', 'total_lines_changed', 'releases_involved']])
    
    # Guardar datos en crudo para futura consulta / filtrado inteligente
    csv_path = os.path.join(OUTPUT_DIR, "evolution_data_raw.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nDatos crudos guardados en: {csv_path}")
    
    # Generar gráficos
    generate_plots(df)
    print(f"Gráficos estadísticos guardados en: {OUTPUT_DIR}")

    # Sugerencia de filtrado inteligente en consola
    median_commits = df['commits'].median()
    median_lines = df['total_lines_changed'].median()
    
    valuable_files = df[(df['commits'] > median_commits) & (df['total_lines_changed'] > median_lines)]
    print("\n--- SUGERENCIA DE FILTRADO PARA AHORRAR PRESUPUESTO ---")
    print(f"Si filtramos archivos que estén por encima de la mediana en commits (>{median_commits}) "
          f"y líneas cambiadas (>{median_lines}):")
    print(f"Nos quedamos con {len(valuable_files)} archivos altamente evolutivos de un total de {len(df)}.")

if __name__ == "__main__":
    main()