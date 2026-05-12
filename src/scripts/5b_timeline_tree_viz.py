#!/usr/bin/env python3
import json
import argparse
import logging
import hashlib
import re
from pathlib import Path
import html
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

sys.path.append(str(get_project_root()))
try:
    from src.domain.models import AgentASTDocument
except ImportError as e:
    logger.error(f"FATAL ERROR: Missing dependencies. {e}")
    sys.exit(1)

# =====================================================================
# SOLUCIÓN DE IDENTIDAD ESTABLE (ROBUST ID)
# =====================================================================
# A diferencia de 5a que hasheaba todo el texto, aquí normalizamos el 
# string (sin puntuación, minúsculas, sin espacios extra) y extraemos
# los primeros 40 caracteres como "firma". Si se edita el final de una
# regla, mantendrá el mismo ID, permitiendo trazar su línea de vida.
# =====================================================================
def get_robust_id(text: str) -> str:
    if not text: return "empty"
    # Solo alfanuméricos y espacios, a minúsculas
    normalized = "".join(c for c in text.lower() if c.isalnum() or c.isspace())
    # Colapsar espacios múltiples
    normalized = " ".join(normalized.split())
    # Tomar la firma (primeros 40 caracteres)
    signature = normalized[:40]
    return hashlib.md5(signature.encode('utf-8')).hexdigest()[:10]

def extract_timeline_lifelines(repo_name: str) -> dict:
    root_dir = get_project_root()
    json_dir = root_dir / "dataset" / "evolution_exp" / "json_trees" / "migrated_jsons" / repo_name
    file_history_path = root_dir / "dataset" / "evolution_exp" / "file_history.json"
    
    if not json_dir.exists():
        return None

    commit_order = []
    if file_history_path.exists():
        try:
            history_data = json.loads(file_history_path.read_text(encoding='utf-8'))
            if repo_name in history_data:
                commit_order = [c['sha'] if isinstance(c, dict) else c for c in history_data[repo_name]]
        except Exception:
            pass

    json_files = list(json_dir.glob("*.json"))
    if not commit_order:
        json_files.sort(key=lambda x: x.stat().st_mtime)
    else:
        def get_index(filepath):
            sha = filepath.stem
            return commit_order.index(sha) if sha in commit_order else 9999
        json_files.sort(key=get_index)
        
    commits_shas = []
    
    # Estructura para rastrear la vida de las reglas
    # dict: unique_id -> { "name", "category", "label", "active_commits": [idx1, idx2...] }
    lifelines_db = {}

    # Invertimos para procesar del más antiguo al más nuevo cronológicamente
    json_files = list(reversed(json_files))

    for c_idx, j_path in enumerate(json_files):
        sha = j_path.stem
        commits_shas.append(sha)
        try:
            data = json.loads(j_path.read_text(encoding='utf-8'))
            doc = AgentASTDocument.model_validate(data)
            
            for cat in doc.rootNode.children:
                if getattr(cat, 'count', -1) == 0: continue
                for label in cat.children:
                    for rule in label.children:
                        text = rule.content.text if (hasattr(rule, 'content') and rule.content) else ""
                        rule_label = getattr(rule, 'short_label', None)
                        if not rule_label or rule_label == "Rule":
                            rule_label = text.strip().split('\n')[0][:60] + "..." if text else "Empty Rule"
                        
                        # ID compuesto para evitar colisiones entre categorías
                        rule_id = f"{cat.label}_{label.label}_{get_robust_id(text)}"
                        
                        if rule_id not in lifelines_db:
                            lifelines_db[rule_id] = {
                                "id": rule_id,
                                "name": rule_label,
                                "category": cat.label,
                                "label": label.label,
                                "cat_color": getattr(cat, 'color', "#94a3b8"),
                                "raw_text": text,
                                "active_commits": []
                            }
                        lifelines_db[rule_id]["active_commits"].append(c_idx)
        except Exception as e:
            logger.error(f"Error en {sha}: {e}")

    # Convertir dict a array y ordenar jerárquicamente
    rules_list = list(lifelines_db.values())
    rules_list.sort(key=lambda x: (x["category"], x["label"], x["name"]))

    return {
        "repo_name": repo_name,
        "commits": commits_shas,
        "rules": rules_list
    }

def generate_html(data: dict, output_path: Path):
    repo_name = html.escape(data["repo_name"])
    timeline_json = json.dumps(data)

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Timeline Tree: {repo_name}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ font-family: system-ui, sans-serif; margin: 0; padding: 0; background: #f8fafc; color: #1e293b; overflow-x: hidden; }}
        .header {{ background: #1e293b; color: white; padding: 15px 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); position: sticky; top:0; z-index: 100; }}
        h1 {{ margin: 0; font-size: 1.2rem; }}
        #viz-container {{ padding: 20px; overflow-x: auto; background: white; margin: 20px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        
        .axis-text {{ font-size: 11px; fill: #64748b; font-family: monospace; }}
        .rule-text {{ font-size: 12px; fill: #334155; cursor: pointer; }}
        .rule-text:hover {{ fill: #2563eb; font-weight: bold; }}
        .lifeline-bg {{ stroke: #e2e8f0; stroke-width: 4px; stroke-linecap: round; }}
        .lifeline-active {{ stroke-width: 4px; stroke-linecap: round; transition: all 0.3s; cursor: pointer; }}
        .lifeline-active:hover {{ stroke-width: 6px; filter: brightness(0.8); }}
        
        .category-bg {{ fill: #f1f5f9; rx: 4; }}
        .category-text {{ font-size: 14px; font-weight: bold; fill: #0f172a; }}
        .label-text {{ font-size: 12px; font-weight: bold; fill: #475569; font-style: italic; }}
        
        #tooltip {{ position: absolute; background: rgba(15,23,42,0.95); color: white; padding: 12px; border-radius: 6px; font-size: 12px; pointer-events: none; opacity: 0; max-width: 350px; z-index: 200; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }}
        #tooltip pre {{ white-space: pre-wrap; color: #a5b4fc; font-family: monospace; margin-top: 8px; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Timeline Tree (Lifelines) - {repo_name}</h1>
        <p style="margin: 5px 0 0 0; font-size: 0.85rem; color: #94a3b8;">X-Axis: Commits over time. Y-Axis: Rule existence. Continuous lines show rule survival.</p>
    </div>
    
    <div id="tooltip"></div>
    <div id="viz-container"></div>

    <script>
        const data = {timeline_json};
        const commits = data.commits;
        const rules = data.rules;
        
        // Dimensions
        const margin = {{top: 40, right: 40, bottom: 20, left: 250}};
        const commitWidth = 40;
        const width = Math.max(800, margin.left + (commits.length * commitWidth) + margin.right);
        
        // Calcular altura dinámica basada en agrupaciones
        let currentY = margin.top;
        let yPositions = {{}};
        let drawCalls = [];
        
        let currentCat = null;
        let currentLabel = null;
        
        rules.forEach(rule => {{
            if(rule.category !== currentCat) {{
                currentCat = rule.category;
                currentLabel = null;
                drawCalls.push({{ type: 'category', text: currentCat, y: currentY, color: rule.cat_color }});
                currentY += 30;
            }}
            if(rule.label !== currentLabel) {{
                currentLabel = rule.label;
                drawCalls.push({{ type: 'label', text: currentLabel, y: currentY }});
                currentY += 25;
            }}
            
            yPositions[rule.id] = currentY;
            drawCalls.push({{ type: 'rule', rule: rule, y: currentY }});
            currentY += 20;
        }});
        
        const height = currentY + margin.bottom;

        const svg = d3.select("#viz-container").append("svg")
            .attr("width", width)
            .attr("height", height);
            
        // Escala X para commits
        const xScale = d3.scalePoint()
            .domain(d3.range(commits.length))
            .range([margin.left, width - margin.right])
            .padding(0.5);
            
        // Eje X (Commits arriba)
        const xAxis = svg.append("g")
            .attr("transform", `translate(0, ${{margin.top - 10}})`);
            
        commits.forEach((c, i) => {{
            xAxis.append("text")
                .attr("class", "axis-text")
                .attr("x", xScale(i))
                .attr("y", 0)
                .attr("text-anchor", "middle")
                .text(c.substring(0, 6));
                
            // Grid lines verticales
            svg.append("line")
                .attr("x1", xScale(i)).attr("x2", xScale(i))
                .attr("y1", margin.top).attr("y2", height - margin.bottom)
                .attr("stroke", "#f1f5f9").attr("stroke-dasharray", "4,4");
        }});

        const tooltip = d3.select("#tooltip");

        // Dibujar Y-Axis (Estructura)
        drawCalls.forEach(item => {{
            if (item.type === 'category') {{
                svg.append("rect")
                    .attr("x", 10).attr("y", item.y - 18)
                    .attr("width", margin.left - 20).attr("height", 24)
                    .attr("fill", item.color).attr("opacity", 0.2).attr("rx", 4);
                svg.append("text")
                    .attr("class", "category-text")
                    .attr("x", 15).attr("y", item.y).text(item.text);
                    
                // Separador horizontal
                svg.append("line").attr("x1", 10).attr("x2", width - margin.right)
                    .attr("y1", item.y + 8).attr("y2", item.y + 8)
                    .attr("stroke", item.color).attr("stroke-opacity", 0.3);
            }} 
            else if (item.type === 'label') {{
                svg.append("text")
                    .attr("class", "label-text")
                    .attr("x", 30).attr("y", item.y).text("↳ " + item.text);
            }} 
            else if (item.type === 'rule') {{
                const r = item.rule;
                // Etiqueta de la regla
                svg.append("text")
                    .attr("class", "rule-text")
                    .attr("x", 45).attr("y", item.y + 4)
                    .text(r.name.length > 30 ? r.name.substring(0,27)+"..." : r.name)
                    .on("mouseover", (e) => {{
                        tooltip.style("opacity", 1)
                            .html(`<strong>${{r.name}}</strong><br>Added in: Commit ${{r.active_commits[0]}}<pre>${{r.raw_text}}</pre>`);
                    }})
                    .on("mousemove", (e) => tooltip.style("left", (e.pageX + 15) + "px").style("top", (e.pageY + 15) + "px"))
                    .on("mouseout", () => tooltip.style("opacity", 0));

                // Fondo de línea de vida (gris tenue para todo el rango posible)
                svg.append("line")
                    .attr("class", "lifeline-bg")
                    .attr("x1", xScale(0)).attr("x2", xScale(commits.length - 1))
                    .attr("y1", item.y).attr("y2", item.y);

                // Dibujar segmentos activos continuos
                let segments = [];
                let currentSeg = [];
                
                r.active_commits.sort((a,b)=>a-b).forEach(idx => {{
                    if (currentSeg.length === 0) {{
                        currentSeg.push(idx);
                    }} else if (idx === currentSeg[currentSeg.length - 1] + 1) {{
                        currentSeg.push(idx);
                    }} else {{
                        segments.push([...currentSeg]);
                        currentSeg = [idx];
                    }}
                }});
                if (currentSeg.length > 0) segments.push(currentSeg);

                segments.forEach(seg => {{
                    const startX = xScale(seg[0]);
                    const endX = xScale(seg[seg.length - 1]);
                    
                    svg.append("line")
                        .attr("class", "lifeline-active")
                        .attr("stroke", r.cat_color)
                        .attr("x1", startX).attr("x2", startX === endX ? startX + 5 : endX)
                        .attr("y1", item.y).attr("y2", item.y)
                        .on("mouseover", (e) => {{
                            tooltip.style("opacity", 1)
                                .html(`<strong>Active Segment</strong><br>From commit index ${{seg[0]}} to ${{seg[seg.length-1]}}`);
                        }})
                        .on("mousemove", (e) => tooltip.style("left", (e.pageX + 15) + "px").style("top", (e.pageY + 15) + "px"))
                        .on("mouseout", () => tooltip.style("opacity", 0));
                        
                    // Dibujar circulitos en cada commit donde existe
                    seg.forEach(idx => {{
                        svg.append("circle")
                            .attr("cx", xScale(idx)).attr("cy", item.y)
                            .attr("r", 3).attr("fill", "#fff")
                            .attr("stroke", r.cat_color).attr("stroke-width", 2);
                    }});
                }});
            }}
        }});
    </script>
</body>
</html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Timeline Tree generado en: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generar Timeline Tree (Lifelines).")
    parser.add_argument("repo_name", type=str, help="Repository folder name")
    args = parser.parse_args()

    data = extract_timeline_lifelines(args.repo_name)
    if not data:
        sys.exit(1)

    out_dir = get_project_root() / "dataset" / "evolution_exp" / "visualizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    generate_html(data, out_dir / f"{args.repo_name}_5b_timeline_tree.html")

if __name__ == "__main__":
    main()