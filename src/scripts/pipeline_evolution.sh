#!/bin/bash
set -e

# Asegurarnos de ejecutar desde la raíz del proyecto
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$PROJECT_ROOT"

if [ $# -eq 0 ]; then
    echo "Uso: ./src/scripts/pipeline_evolution.sh [NOMBRE_REPO]"
    echo "Ejemplo: ./src/scripts/pipeline_evolution.sh deeeed_audiolab"
    exit 1
fi

REPO_NAME="$1"

# Definición de las NUEVAS rutas
INPUT_DIR="dataset/evolution_exp/json_trees/llm_api/$REPO_NAME"
INTERMEDIATE_DIR="dataset/evolution_exp/json_trees/migrated_jsons/$REPO_NAME" # <--- ¡Cambiado!
OUTPUT_DIR="dataset/evolution_exp/llm_api/$REPO_NAME"
DEFAULT_VIZ_DIR="dataset/visualizations" 

# Verificar que el directorio del repositorio exista
if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ Error: El directorio $INPUT_DIR no existe."
    exit 1
fi

# Crear directorios si no existen
mkdir -p "$INTERMEDIATE_DIR"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$DEFAULT_VIZ_DIR"

# Activar entorno virtual
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "=========================================================="
echo "    AgentLens Evolution Pipeline - Repo: $REPO_NAME       "
echo "=========================================================="

TOTAL_FILES=$(ls -1 "$INPUT_DIR"/*.json 2>/dev/null | wc -l)

if [ "$TOTAL_FILES" -eq 0 ]; then
    echo "⚠️ No se encontraron archivos .json en $INPUT_DIR"
    exit 1
fi

CURRENT_FILE=1

for INPUT_JSON in "$INPUT_DIR"/*.json; do
    JSON_NAME=$(basename "$INPUT_JSON")
    BASE_NAME="${JSON_NAME%.*}"
    INTERMEDIATE_JSON="$INTERMEDIATE_DIR/$JSON_NAME"
    
    echo -e "\n► Procesando archivo [$CURRENT_FILE/$TOTAL_FILES]: $JSON_NAME"

    echo "  [1/2] Alineando Topología V2 (Macro-Categorías)..."
    python src/scripts/2z_migrate_ast_schema.py "$INPUT_JSON" "$INTERMEDIATE_JSON"

    echo "  [2/2] Calculando Densidades D3.js (HTML)..."
    # Llamamos al nuevo script dedicado a evolución
    PYTHONPATH=. python src/scripts/4f_evolution_viz.py "$INTERMEDIATE_JSON"

    # Mover el HTML generado a la carpeta final de evolución
    EXPECTED_HTML="$DEFAULT_VIZ_DIR/${BASE_NAME}_tree_viz.html"
    FINAL_HTML="$OUTPUT_DIR/${BASE_NAME}_tree_viz.html"

    if [ -f "$EXPECTED_HTML" ]; then
        mv "$EXPECTED_HTML" "$FINAL_HTML"
        echo "  ✅ Guardado en: $FINAL_HTML"
    else
        echo "  ⚠️ Advertencia: No se encontró el HTML en $EXPECTED_HTML."
    fi

    CURRENT_FILE=$((CURRENT_FILE + 1))
done

echo -e "\n=========================================================="
echo " ✅ Pipeline de Evolución Exitoso para: $REPO_NAME"
echo " 📁 Migrados JSON: $INTERMEDIATE_DIR/"
echo " 🌐 Visualizaciones HTML: $OUTPUT_DIR/"
echo "=========================================================="