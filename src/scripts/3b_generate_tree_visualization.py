#!/usr/bin/env python3
import json
import argparse
import logging
from pathlib import Path
import html
import textstat

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

import sys
# Add src parent to the python path so imports resolve
sys.path.append(str(get_project_root()))
try:
    from src.domain.models import AgentASTDocument, RuleCategory
except ImportError as e:
    logger.error(f"FATAL ERROR: Missing dependencies. Ensure your virtual environment is activated. Details: {e}")
    sys.exit(1)

def escape(text):
    if not text:
        return ""
    return html.escape(str(text))

def calculate_category_fre(cat) -> float:
    """
    JUSTIFICACIÓN ACADÉMICA: El cálculo de Flesch-Kincaid se aplica a nivel de categoría concatenando sus instrucciones. 
    No se aplica a nivel de instrucción individual porque las fórmulas de legibilidad pierden validez estadística y generan 
    ruido en textos cortos (menores a 100 palabras). Concatenar por categoría ofrece una medida real de la densidad 
    cognitiva de esa sección del documento.
    """
    if not cat.children:
        return 100.0
    
    # Flesch-Kincaid evaluates legibility on text length and syllables. So we concatenate the label's sub-rules.
    if not hasattr(cat, 'children') or not cat.children:
        return 100.0
    
    concatenated_text = " ".join(rule.content.text for rule in cat.children if hasattr(rule, 'content'))
    
    if not concatenated_text.strip():
        return 100.0
    
    try:
        fre = textstat.flesch_reading_ease(concatenated_text)
        return max(0.0, fre)  # Dense tech text can be mathematically negative; clamp to 0 for UI bounds
    except:
        return 50.0

def build_tree_data(doc):
    """Converts the Domain Model AST into a hierarchical structure expected by d3.hierarchy()"""
    
    # Root Node
    tree = {
        "name": doc.repo_name,
        "group": "root",
        "width": doc.tree_width,
        "height": doc.tree_height,
        "color": doc.root_color,
        "border_width": 2,
        "details": doc.root_html_details,
        "children": []
    }
    
    for cat in doc.rootNode.children:
        if cat.count == 0:
            continue
            
        cat_node = {
            "name": cat.label,
            "group": "category",
            "width": cat.tree_width,
            "height": cat.tree_height,
            "color": cat.color,
            "border_width": cat.border_width,
            "details": cat.html_details,
            "children": []
        }
        
        for label in cat.children:
            fre_score = calculate_category_fre(label)
            label.fre_score = fre_score
            
            label_node = {
                "name": label.label,
                "group": "label",
                "width": label.tree_width,
                "height": label.tree_height,
                "color": label.color,
                "border_width": label.border_width,
                "fre_score": round(fre_score, 1),
                "details": label.html_details,
                "children": []
            }
            
            for rule in label.children:
                label_node["children"].append({
                    "name": rule.short_label,
                    "group": "rule",
                    "width": rule.tree_width,
                    "height": rule.tree_height,
                    "color": rule.color,
                    "border_width": 1.5,
                    "raw_text": rule.content.text, 
                    "details": rule.html_details,
                    "strength": rule.metadata.strength,
                    "value": 1
                })
                
            cat_node["children"].append(label_node)
            
        tree["children"].append(cat_node)
            
    return json.dumps(tree)

def generate_html(md_content, doc, output_path):
    repo_name = escape(doc.repo_name)
    md_source = escape(doc.source_file)
    escaped_md = escape(md_content)
    
    # Transform Domain AST to D3 Hierarchical JSON
    tree_json_str = build_tree_data(doc)

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AST Tree View: {repo_name}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            height: 100vh;
            background-color: #f1f5f9;
            color: #334155;
            overflow: hidden;
        }}
        .header-bar {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 50px;
            background: #1e293b;
            color: white;
            display: flex;
            align-items: center;
            padding: 0 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            z-index: 10;
        }}
        .header-title {{ margin: 0; font-size: 1.2rem; }}
        
        .split-container {{
            display: flex;
            width: 100%;
            height: calc(100vh - 50px);
            margin-top: 50px;
        }}
        
        .left-pane {{
            flex: 0 0 40%;
            overflow-y: auto;
            padding: 20px;
            background: #ffffff;
            border-right: 2px solid #cbd5e1;
            box-sizing: border-box;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            white-space: pre-wrap;
            color: #475569;
        }}
        
        .right-pane {{
            flex: 1;
            position: relative;
            background: #f8fafc;
            display: flex;
            flex-direction: column;
        }}
        
        #graph-container {{
            flex: 1;
            width: 100%;
            height: 100%;
            cursor: grab;
        }}
        #graph-container:active {{ cursor: grabbing; }}
        
        .pane-title {{
            position: absolute;
            top: 20px;
            left: 20px;
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748b;
            margin: 0;
            z-index: 5;
            pointer-events: none;
        }}
        
        #details-panel {{
            position: absolute;
            top: 20px;
            right: 20px;
            width: 300px;
            max-height: calc(100% - 40px);
            overflow-y: auto;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            display: none;
            z-index: 5;
            font-size: 0.95rem;
            line-height: 1.5;
        }}
        #details-panel h3 {{ margin-top: 0; color: #0f172a; font-size: 1.1rem; }}
        #details-panel .close-btn {{
            position: absolute;
            top: 10px;
            right: 15px;
            cursor: pointer;
            color: #94a3b8;
            font-weight: bold;
        }}
        #details-panel .close-btn:hover {{ color: #0f172a; }}
        
        .node circle {{
            stroke: #fff;
            stroke-width: 2px;
            cursor: pointer;
        }}
        .node:hover circle {{
            stroke: #334155;
            stroke-width: 3px;
        }}
        
        .node text {{
            font-size: 11px;
            font-family: -apple-system, sans-serif;
            pointer-events: none;
        }}
        
        .link {{
            fill: none;
            stroke: #cbd5e1;
            stroke-width: 1.5px;
        }}

        .legend {{
            display: none; /* Temporarily hidden for testing purposes */
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(255,255,255,0.9);
            padding: 10px;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            font-size: 0.8rem;
            pointer-events: none;
        }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 5px; }}
        .legend-color {{ width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }}
    </style>
</head>
<body>
    <div class="header-bar">
        <h1 class="header-title">{repo_name} - Strict Hierarchical Tree V1</h1>
    </div>
    
    <div class="split-container">
        <div class="left-pane" id="markdown-content">
            <h2 style="font-size: 1.1rem; text-transform: uppercase; color: #64748b; margin-top: 0; padding-bottom: 10px; border-bottom: 1px solid #e2e8f0; margin-bottom: 20px; font-family: sans-serif;">Raw Document ({md_source})</h2>
            {escaped_md}
        </div>
        
        <div class="right-pane">
            <h2 class="pane-title">Hierarchical AST Tree</h2>
            
            <div id="graph-container"></div>
            
            <div id="details-panel">
                <span class="close-btn" onclick="document.getElementById('details-panel').style.display='none'">✕</span>
                <h3>Node Details</h3>
                <div id="details-content">Click a node to view its structural properties and rules.</div>
            </div>
            
            <div class="legend">
                <strong>Visual Encoding</strong>
                <div class="legend-item"><div class="legend-color" style="background: #1e293b;"></div> Root Node</div>
                <div class="legend-item"><div class="legend-color" style="background: #eab308;"></div> Rule Instruction</div>
                <br>
                <strong>Category & Label Encodings</strong>
                <div class="legend-item" style="margin-bottom: 2px;">📏 <strong>Height:</strong> Sub-items text density (40-120px)</div>
                <div class="legend-item" style="margin-bottom: 2px;">↔️ <strong>Width:</strong> Number of nested rules (max 200px)</div>
                <div class="legend-item">🔳 <strong>Border Density:</strong> Code presence multiplier</div>
                <br>
                <strong>Category Color = FRE Score</strong>
                <div class="legend-item"><div class="legend-color" style="background: #ef4444;"></div> &lt;30 High Load (Complex)</div>
                <div class="legend-item"><div class="legend-color" style="background: #f97316;"></div> 30-50 Med-High Load</div>
                <div class="legend-item"><div class="legend-color" style="background: #eab308;"></div> 50-70 Medium Load</div>
                <div class="legend-item"><div class="legend-color" style="background: #22c55e;"></div> &gt;70 Low Load (Easy)</div>
                <br>
                <small><em>Hint: Click nodes to expand/collapse.</em></small>
            </div>
        </div>
    </div>

    <script>
        const treeData = {tree_json_str};

        const container = document.getElementById("graph-container");
        const width = container.clientWidth;
        const height = container.clientHeight;

        const svg = d3.select("#graph-container")
            .append("svg")
            .attr("width", width)
            .attr("height", height);
            
        const g = svg.append("g");
        
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
            
        svg.call(zoom);

        let root = d3.hierarchy(treeData);
        let i = 0;
        
        // Progressive disclosure: Collapse all labels (depth 1 children) initially
        root.descendants().forEach(d => {{
            if (d.depth >= 1) {{ 
                d._children = d.children;
                d.children = null;
            }}
        }});

        // Config layout: dx controls base vertical spacing unit, dy controls horizontal depth spread
        const dx = 1;  
        const dy = 320; 
        const treeLayout = d3.tree()
            .nodeSize([dx, dy])
            .separation((a, b) => {{
                // Read exact rectangle height defined by the server (or fallback 40px)
                const hA = a.data.height || 40;
                const hB = b.data.height || 40;
                
                // Keep 30px vertical padding between the borders of the bounding boxes
                return (hA + hB) / 2 + 30;
            }});
        
        // Containers
        g.append("g").attr("class", "links");
        g.append("g").attr("class", "nodes");
        
        // Base center
        g.attr("transform", `translate(${{dy / 2}},${{height / 2}})`);

        function update(source) {{
            treeLayout(root);
            
            const nodes = root.descendants();
            const links = root.links();
            
            // LINKS
            const link = g.select(".links").selectAll("path.link")
                .data(links, d => d.target.id || (d.target.id = ++i));
                
            const linkEnter = link.enter().append("path")
                .attr("class", "link")
                .attr("d", d => {{
                    const o = {{x: source.x0 || source.x, y: source.y0 || source.y}};
                    return d3.linkHorizontal().x(d => d.y).y(d => d.x)({{source: o, target: o}});
                }});
                
            link.merge(linkEnter).transition().duration(400)
                .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x));
                
            link.exit().transition().duration(400)
                .attr("d", d => {{
                    const o = {{x: source.x, y: source.y}};
                    return d3.linkHorizontal().x(d => d.y).y(d => d.x)({{source: o, target: o}});
                }}).remove();
                
            // NODES
            const node = g.select(".nodes").selectAll("g.node")
                .data(nodes, d => d.id || (d.id = ++i));
                
            const nodeEnter = node.enter().append("g")
                .attr("class", "node")
                .attr("transform", d => `translate(${{source.y0 || source.y}},${{source.x0 || source.x}})`)
                .on("click", (event, d) => {{
                    showDetails(d.data, event.currentTarget);
                    if (d.data.group === "rule" && d.data.raw_text) {{
                        highlightTextInLeftPane(d.data.raw_text);
                    }} else {{
                        clearHighlightInLeftPane();
                    }}
                    
                    if (d.children) {{
                        d._children = d.children;
                        d.children = null;
                    }} else if (d._children) {{
                        d.children = d._children;
                        d._children = null;
                    }}
                    if (d.data.group !== "rule") {{
                        update(d);
                    }}
                }});
                
            // Rectangles
            nodeEnter.append("rect")
                .attr("class", "main-rect")
                .attr("width", d => d.data.width || 120)
                .attr("height", d => d.data.height || 40)
                .attr("y", d => -(d.data.height || 40) / 2)
                .attr("rx", 6).attr("ry", 6)
                .attr("fill", d => d.data.color)
                .attr("stroke-width", d => d.data.border_width || 2)
                .attr("stroke", d => d._children ? "#0f172a" : "#cbd5e1");
                
            // Text inside Rects
            nodeEnter.append("text")
                .attr("dy", "0.31em")
                .attr("x", 12)
                .attr("text-anchor", "start")
                .text(d => d.data.name)
                .style("fill", d => d.data.group === "root" ? "#fff" : "#0f172a")
                .style("font-weight", "500");
                
            // Transitions
            const nodeUpdate = nodeEnter.merge(node);
            
            nodeUpdate.transition().duration(400)
                .attr("transform", d => `translate(${{d.y}},${{d.x}})`);
                
            nodeUpdate.select("rect").transition().duration(400)
                .attr("stroke", d => d._children ? "#0f172a" : "#cbd5e1");
                
            node.exit().transition().duration(400)
                .attr("transform", d => `translate(${{source.y}},${{source.x}})`)
                .style("opacity", 0)
                .remove();
                
            nodes.forEach(d => {{
                d.x0 = d.x;
                d.y0 = d.y;
            }});
        }}
        
        root.x0 = height / 2;
        root.y0 = 0;
        update(root);

        function showDetails(nodeData, nodeElement) {{
            const panel = document.getElementById("details-panel");
            const content = document.getElementById("details-content");
            
            let html = `<strong>${{nodeData.group.toUpperCase()}}</strong><br>`;
            html += nodeData.details;
            
            content.innerHTML = html;
            panel.style.display = "block";
            
            d3.selectAll("rect.main-rect").style("stroke", function(d) {{ return d._children ? "#0f172a" : "#cbd5e1"; }});
            d3.select(nodeElement).select("rect.main-rect").style("stroke", "#0f172a");
        }}

        window.addEventListener("resize", () => {{
            const newWidth = container.clientWidth;
            const newHeight = container.clientHeight;
            svg.attr("width", newWidth).attr("height", newHeight);
        }});

        // Guarda el texto plano original del left pane (una sola vez)
        const leftPaneEl = document.getElementById("markdown-content");
        const originalLeftHtml = leftPaneEl.innerHTML;

        function escapeRegex(s) {{
            return s.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
        }}

        function highlightTextInLeftPane(searchText) {{
            // 1. Restaurar HTML limpio
            leftPaneEl.innerHTML = originalLeftHtml;

            if (!searchText || searchText.trim() === "") return;

            try {{
                // 2. Extraer solo palabras alfanuméricas del raw_text
                const words = searchText.match(/[A-Za-z0-9\u00C0-\u017F]+/g);
                if (!words || words.length === 0) return;

                // Limitar palabras para evitar bloqueo en reglas largas
                const searchWords = words.length > 20 ? [...words.slice(0, 10), ...words.slice(-5)] : words;

                // 3. Escapar cada palabra como literal de regex y unirlas con
                //    [\\s\\S]{{0,80}}? para permitir cualquier carácter entre ellas
                //    (incluyendo tags HTML, entidades, saltos de línea, símbolos markdown)
                const parts = searchWords.map(w => escapeRegex(w));
                const fuzzyPattern = parts.join('[\\\\s\\\\S]{{0,80}}?');
                const regex = new RegExp('(' + fuzzyPattern + ')', 'gi');

                let matchFound = false;

                // 4. Aplicar resaltado directamente sobre el innerHTML
                leftPaneEl.innerHTML = originalLeftHtml.replace(regex, (match) => {{
                    matchFound = true;
                    return '<mark style="background-color:#fce7f3;color:#9d174d;padding:2px 0;border-radius:2px;font-weight:bold;box-shadow:0 0 4px #fbcfe8;">' + match + '</mark>';
                }});

                // 5. Autoscroll al primer match
                if (matchFound) {{
                    const mark = leftPaneEl.querySelector("mark");
                    if (mark) mark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }} else {{
                    console.warn("[highlight] No match found for:", searchText);
                }}
            }} catch (e) {{
                console.error("[highlight] Failed:", e);
            }}
        }}

        function clearHighlightInLeftPane() {{
            leftPaneEl.innerHTML = originalLeftHtml;
        }}
    </script>
</body>
</html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Successfully generated Hierarchical Tree visualization: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate Hierarchical Tree HTML Graph from Phase 2 AST.")
    parser.add_argument("json_file", type=str, help="Path to the extracted JSON AST file")
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        logger.error(f"Error: JSON file {json_path} does not exist.")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON: {e}")
        return

    try:
        doc = AgentASTDocument.model_validate(json_data)
    except Exception as e:
        logger.error(f"Failed to validate Domain Model from JSON: {e}")
        return

    md_source = doc.source_file
    if not md_source:
        logger.error("Domain Model is missing 'agentsMdSource'. Cannot find raw markdown.")
        return

    root_dir = get_project_root()
    md_path_exp = root_dir / "dataset" / "enriched_agents_temp" / md_source
    md_path_cache = root_dir / "dataset" / "enriched_agents" / md_source
    
    md_path = md_path_cache
    if not md_path.exists() and md_path_exp.exists():
        md_path = md_path_exp
    
    if not md_path.exists():
        logger.error(f"Raw markdown file not found at: {md_path}")
        return

    try:
        md_content = md_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to read markdown file: {e}")
        return

    output_dir = root_dir / "dataset" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{json_path.stem}_tree_viz.html"
    generate_html(md_content, doc, output_path)

if __name__ == "__main__":
    main()