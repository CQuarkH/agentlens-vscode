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
    if not cat.children:
        return 100.0
    
    if not hasattr(cat, 'children') or not cat.children:
        return 100.0
    
    concatenated_text = " ".join(rule.content.text for rule in cat.children if hasattr(rule, 'content'))
    
    if not concatenated_text.strip():
        return 100.0
    
    try:
        fre = textstat.flesch_reading_ease(concatenated_text)
        return max(0.0, fre)
    except:
        return 50.0

def build_tree_data(doc):
    all_rule_lengths = []
    for cat in doc.rootNode.children:
        for label in cat.children:
            for rule in label.children:
                all_rule_lengths.append(len(rule.content.text) if rule.content.text else 0)
                
    min_len = min(all_rule_lengths) if all_rule_lengths else 0
    max_len = max(all_rule_lengths) if all_rule_lengths else 1
    if min_len == max_len:
        max_len = min_len + 1 

    MIN_WIDTH = 120
    MAX_WIDTH = 350

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
                text_len = len(rule.content.text) if rule.content.text else 0
                normalized_width = MIN_WIDTH + ((text_len - min_len) / (max_len - min_len)) * (MAX_WIDTH - MIN_WIDTH)
                
                label_node["children"].append({
                    "name": rule.short_label,
                    "group": "rule",
                    "width": round(normalized_width),
                    "height": rule.tree_height,
                    "color": label.color,
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
            display: flex;
            flex-direction: column;
            background: #ffffff;
            border-right: 2px solid #cbd5e1;
            box-sizing: border-box;
        }}

        .left-pane-header {{
            padding: 20px;
            border-bottom: 1px solid #e2e8f0;
        }}

        #markdown-content {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
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
    </style>
</head>
<body>
    <div class="header-bar">
        <h1 class="header-title">{repo_name} - Strict Hierarchical Tree V1</h1>
    </div>
    
    <div class="split-container">
        <div class="left-pane">
            <div class="left-pane-header">
                <h2 style="font-size: 1.1rem; text-transform: uppercase; color: #64748b; margin: 0; font-family: sans-serif;">Raw Document ({md_source})</h2>
            </div>
            <!-- Separamos el contenido para no romper el HTML del <h2> con el Regex -->
            <div id="markdown-content">{escaped_md}</div>
        </div>
        
        <div class="right-pane">
            <h2 class="pane-title">Hierarchical AST Tree</h2>
            
            <div id="graph-container"></div>
            
            <div id="details-panel">
                <span class="close-btn" onclick="document.getElementById('details-panel').style.display='none'">✕</span>
                <h3>Node Details</h3>
                <div id="details-content">Click a node to view its structural properties and rules.</div>
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
        
        root.descendants().forEach(d => {{
            if (d.depth >= 1) {{ 
                d._children = d.children;
                d.children = null;
            }}
        }});

        const dx = 1;  
        const dy = 320; 
        const treeLayout = d3.tree()
            .nodeSize([dx, dy])
            .separation((a, b) => {{
                const hA = a.data.height || 40;
                const hB = b.data.height || 40;
                return (hA + hB) / 2 + 30;
            }});
        
        g.append("g").attr("class", "links");
        g.append("g").attr("class", "nodes");
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
                        highlightTextInLeftPane(d.data.raw_text, d.data.color);
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
                
            nodeEnter.filter(d => d.data.group !== "root").append("rect")
                .attr("class", "main-rect")
                .attr("width", d => d.data.width || 120)
                .attr("height", d => d.data.height || 40)
                .attr("y", d => -(d.data.height || 40) / 2)
                .attr("rx", 6).attr("ry", 6)
                .attr("fill", d => d.data.color)
                .attr("stroke-width", d => d.data.border_width || 2)
                .attr("stroke", "#0f172a");
                
            nodeEnter.filter(d => d.data.group === "root")
                .append("image")
                .attr("href", "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23334155' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/></svg>")
                .attr("width", 32)
                .attr("height", 32)
                .attr("x", -16)
                .attr("y", -16);
                
            nodeEnter.append("rect")
                .attr("class", "text-bg")
                .attr("fill", "rgba(255, 255, 255, 0.70)")
                .attr("rx", 3).attr("ry", 3)
                .style("pointer-events", "none");
                
            nodeEnter.append("text")
                .attr("class", "node-label")
                .attr("dy", d => d.data.group === "root" ? "28px" : "0.31em")
                .attr("x", d => d.data.group === "root" ? 0 : 12)
                .attr("text-anchor", d => d.data.group === "root" ? "middle" : "start")
                .text(d => d.data.name)
                .style("fill", "#0f172a") 
                .style("font-weight", "500");
                
            const nodeUpdate = nodeEnter.merge(node);
            
            // --- MODIFICACIÓN 3: Truncar texto de Rules con "..." si supera el ancho ---
            nodeUpdate.select(".node-label").each(function(d) {{
                if (d.data.group === "rule") {{
                    const padding = 24; // Espacio seguro izq y der
                    const maxWidth = (d.data.width || 120) - padding;
                    let textStr = d.data.name;
                    this.textContent = textStr; // Reset al texto completo
                    
                    if (this.getComputedTextLength() > maxWidth && textStr.length > 3) {{
                        let i = textStr.length;
                        while (this.getComputedTextLength() > maxWidth && i > 0) {{
                            i--;
                            this.textContent = textStr.slice(0, i) + "...";
                        }}
                    }}
                }}
            }});

            // --- MODIFICACIÓN 2: Fondo blanco para las Rules también ---
            nodeUpdate.each(function(d) {{
                const textNode = d3.select(this).select(".node-label").node();
                if (textNode && textNode.getBBox) {{
                    const bbox = textNode.getBBox();
                    // Ahora se permite a category, label Y rule tener fondo blanco
                    if (d.data.group === "category" || d.data.group === "label" || d.data.group === "rule") {{
                        d3.select(this).select(".text-bg")
                            .attr("x", bbox.x - 4)
                            .attr("y", bbox.y - 2)
                            .attr("width", bbox.width + 8)
                            .attr("height", bbox.height + 4);
                    }} else {{
                        d3.select(this).select(".text-bg")
                            .attr("width", 0).attr("height", 0);
                    }}
                }}
            }});
            
            nodeUpdate.transition().duration(400)
                .attr("transform", d => `translate(${{d.y}},${{d.x}})`);
                
            nodeUpdate.select("rect").transition().duration(400)
                .attr("stroke", "#0f172a");
                
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
        }}

        window.addEventListener("resize", () => {{
            const newWidth = container.clientWidth;
            const newHeight = container.clientHeight;
            svg.attr("width", newWidth).attr("height", newHeight);
        }});

        const leftPaneEl = document.getElementById("markdown-content");
        const originalLeftHtml = leftPaneEl.innerHTML;

        // Helper: escapa un string para usarlo como literal en un RegExp
        function escapeRegExp(str) {{
            return str.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
        }}

        // Helper: escapa texto igual que html.escape() de Python, para buscar en innerHTML
        function htmlEscape(str) {{
            return str
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }}

        // --- MODIFICACIÓN 1: Regex robusto que opera sobre el HTML escapado ---
        function highlightTextInLeftPane(searchText, highlightColor) {{
            leftPaneEl.innerHTML = originalLeftHtml;
            if (!searchText || searchText.trim() === "") return;

            try {{
                // El originalLeftHtml contiene texto HTML-escapado (ej: & -> &amp;).
                // Debemos escapar el searchText de la misma forma antes de extraer palabras,
                // así el regex opera en el mismo espacio de caracteres que el innerHTML.
                const escapedSearchText = htmlEscape(searchText);

                // Extrae tokens alfanuméricos del texto ya escapado
                // Incluye también secuencias de entidades HTML como &amp; &lt; etc.
                const words = escapedSearchText.match(/(?:&[a-z]+;|[A-Za-z0-9À-ÿ]+)/g);
                if (!words || words.length === 0) return;

                // El separador permite cero o más caracteres no-alfanuméricos entre tokens
                // (espacios, saltos de línea, markdown, entidades HTML parciales, etc.)
                // Usamos *? (cero o más, no-greedy) para no saltar demasiado entre tokens
                const sep = '[^A-Za-z0-9À-ÿ]*?';

                function buildRegexStr(wordList) {{
                    return wordList.map(escapeRegExp).join(sep);
                }}

                function tryHighlight(regexStr) {{
                    const regex = new RegExp('(' + regexStr + ')', 'gi');
                    let matchFound = false;
                    const newHtml = originalLeftHtml.replace(regex, (match) => {{
                        matchFound = true;
                        return `<mark style="background-color:${{highlightColor}};color:#0f172a;padding:2px 0;border-radius:2px;font-weight:bold;box-shadow:0 0 4px ${{highlightColor}};">` + match + '</mark>';
                    }});
                    if (matchFound) {{
                        leftPaneEl.innerHTML = newHtml;
                        const mark = leftPaneEl.querySelector("mark");
                        if (mark) mark.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    }}
                    return matchFound;
                }}

                let matched = false;

                if (words.length <= 15) {{
                    // Texto corto: busca la secuencia completa de tokens
                    matched = tryHighlight(buildRegexStr(words));
                }} else {{
                    // Texto largo: ancla primeras 8 y últimas 8 palabras con gap flexible en el medio
                    const startWords = words.slice(0, 8);
                    const endWords = words.slice(-8);
                    const regexStr = buildRegexStr(startWords) + '[\\\\s\\\\S]{{0,5000}}?' + buildRegexStr(endWords);
                    matched = tryHighlight(regexStr);
                }}

                // FALLBACK 1: Si no hubo match, intenta solo las primeras 8 palabras
                if (!matched) {{
                    const fallbackWords = words.slice(0, 8);
                    matched = tryHighlight(buildRegexStr(fallbackWords));
                }}

                // FALLBACK 2: Si sigue sin match, intenta solo las primeras 4 palabras
                if (!matched) {{
                    const fallbackWords = words.slice(0, 4);
                    matched = tryHighlight(buildRegexStr(fallbackWords));
                }}

                if (!matched) {{
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