import os
import re
import yaml
import shutil

# Configuración de rutas relativas
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATASET_DIR = os.path.join(PROJECT_ROOT, 'dataset')

INPUT_DIR = os.path.join(DATASET_DIR, 'enriched_agents')
OUTPUT_DIR = os.path.join(DATASET_DIR, 'enriched_agents_top_categories')

def extract_frontmatter(content):
    """Extrae y parsea el bloque YAML frontmatter del inicio de un archivo markdown."""
    match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            print(f"Error parseando YAML: {e}")
    return {}

def main():
    if not os.path.exists(INPUT_DIR):
        print(f"Error: El directorio de entrada {INPUT_DIR} no existe.")
        return

    # Crear directorio de salida si no existe
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    archivos_procesados = 0
    archivos_copiados = 0

    print(f"Analizando archivos en: {INPUT_DIR}")
    
    for filename in os.listdir(INPUT_DIR):
        if not filename.endswith('.md'):
            continue
            
        file_path = os.path.join(INPUT_DIR, filename)
        archivos_procesados += 1
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        metadata = extract_frontmatter(content)
        
        # Verificar si tiene la clave 'categories' y si tiene más de 9
        categories = metadata.get('categories', [])
        if isinstance(categories, list) and len(categories) > 9:
            dest_path = os.path.join(OUTPUT_DIR, filename)
            shutil.copy2(file_path, dest_path)
            archivos_copiados += 1
            print(f"  -> Copiado: {filename} ({len(categories)} categorías)")

    print("-" * 30)
    print(f"Total analizados: {archivos_procesados}")
    print(f"Total copiados (> 3 categorías): {archivos_copiados}")
    print(f"Destino: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()