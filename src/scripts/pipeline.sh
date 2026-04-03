#!/bin/bash
set -e

if [ $# -eq 0 ]; then
    echo "Uso: ./src/scripts/pipeline.sh NombreDelArchivo.md"
    echo "Ejemplo: ./src/scripts/pipeline.sh buger_probe.md"
    exit 1
fi

MD_FILE=$(basename "$1")
BASE_NAME="${MD_FILE%.*}"
JSON_NAME="${BASE_NAME}.json"

# Auto-activate python virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "=============================================="
echo "    AgentLens AST Pipeline - $BASE_NAME       "
echo "=============================================="

echo -e "\n[1/3] Extrayendo Reglas AST Raw (LLM API)..."
python src/scripts/2c_extract_json_llm_api.py "dataset/enriched_agents/$MD_FILE"

echo -e "\n[2/3] Alineando Topología V2 (Macro-Categorías)..."
python src/scripts/2z_migrate_ast_schema.py "dataset/json_trees/llm_api/$JSON_NAME" "dataset/json_trees/llm_forced_output/$JSON_NAME"

echo -e "\n[3/3] Calculando Densidades D3.js (HTML)..."
PYTHONPATH=. python src/scripts/3b_generate_tree_visualization.py "dataset/json_trees/llm_forced_output/$JSON_NAME"

echo -e "\n=============================================="
echo " ✅ Pipeline Exitoso!"
echo " 🌐 Visualización lista en: dataset/visualizations/${BASE_NAME}_tree_viz.html"
echo "=============================================="
