#!/usr/bin/env python3
import json
import argparse
import logging
import hashlib
from pathlib import Path
import html
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

# Importamos los modelos de dominio exactamente igual que en el 4f para heredar sus colores y lógica
sys.path.append(str(get_project_root()))
try:
    from src.domain.models import AgentASTDocument
except ImportError as e:
    logger.error(f"FATAL ERROR: Missing dependencies. Ensure your virtual environment is activated. Details: {e}")
    sys.exit(1)

def get_stable_id(text: str) -> str:
    """Genera un ID único y estable basado en el contenido del texto para D3.js."""
    if not text:
        return "empty"
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:10]

def parse_commit_tree(json_data: dict, commit_sha: str, repo_name: str):
    """Parsea el AST usando Pydantic para obtener los mismos colores y labels que el 4f."""
    try:
        # Esto asigna los colores reales calculados por el backend (idéntico al 4f)
        doc = AgentASTDocument.model_validate(json_data)
    except Exception as e:
        logger.error(f"Failed to validate JSON for commit {commit_sha} using Pydantic: {e}")
        return None

    tree = {
        "id": "root",
        "name": doc.repo_name,
        "group": "root",
        "color": getattr(doc, 'root_color', "#e2e8f0"),
        "children": []
    }
    
    for cat in doc.rootNode.children:
        # Ignoramos categorías vacías igual que hace el 4f
        if getattr(cat, 'count', -1) == 0:
            continue
            
        cat_name = cat.label
        cat_id = f"cat_{cat_name}"
        cat_color = getattr(cat, 'color', "#94a3b8")
        
        cat_node = {
            "id": cat_id,
            "name": cat_name,
            "group": "category",
            "color": cat_color,
            "children": []
        }
        
        for label in cat.children:
            label_name = label.label
            label_id = f"lbl_{cat_name}_{label_name}"
            label_color = getattr(label, 'color', cat_color)
            
            label_node = {
                "id": label_id,
                "name": label_name,
                "group": "label",
                "color": label_color,
                "children": []
            }
            
            for rule in label.children:
                text = rule.content.text if (hasattr(rule, 'content') and rule.content) else ""
                rule_label = getattr(rule, 'short_label', None)
                
                # Si el label es nulo o es un genérico "Rule", autogeneramos uno descriptivo
                if not rule_label or rule_label == "Rule":
                    rule_label = text.strip().split('\n')[0][:60] + "..." if text else "Empty Rule"
                    
                # El ID basado en hash permite que D3 trackee la regla perfectamente si no cambia
                rule_id = f"rule_{cat_name}_{label_name}_{get_stable_id(text)}"
                
                label_node["children"].append({
                    "id": rule_id,
                    "name": rule_label,
                    "group": "rule",
                    "color": label_color,
                    "raw_text": text,
                    "width": min(max(180, len(rule_label) * 7), 400)
                })
                
            if label_node["children"]:
                cat_node["children"].append(label_node)
                
        if cat_node["children"]:
            tree["children"].append(cat_node)
            
    return tree

def extract_timeline_data(repo_name: str) -> dict:
    root_dir = get_project_root()
    json_dir = root_dir / "dataset" / "evolution_exp" / "json_trees" / "migrated_jsons" / repo_name
    file_history_path = root_dir / "dataset" / "evolution_exp" / "file_history.json"
    
    if not json_dir.exists():
        logger.error(f"Directory not found: {json_dir}")
        return None

    commit_order = []
    if file_history_path.exists():
        try:
            history_data = json.loads(file_history_path.read_text(encoding='utf-8'))
            if repo_name in history_data:
                commit_order = [c['sha'] if isinstance(c, dict) else c for c in history_data[repo_name]]
        except Exception as e:
            logger.warning(f"Could not parse file_history.json: {e}")

    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        logger.error(f"No JSON files found in {json_dir}")
        return None

    if not commit_order:
        json_files.sort(key=lambda x: x.stat().st_mtime)
    else:
        def get_index(filepath):
            sha = filepath.stem
            return commit_order.index(sha) if sha in commit_order else 9999
        json_files.sort(key=get_index)

    commits_data = []
    
    for j_path in json_files:
        sha = j_path.stem
        try:
            data = json.loads(j_path.read_text(encoding='utf-8'))
            tree_structure = parse_commit_tree(data, sha, repo_name)
            
            if tree_structure:
                commits_data.append({
                    "commit": sha,
                    "tree": tree_structure
                })
        except Exception as e:
            logger.error(f"Failed to process {j_path.name}: {e}")

    # Invertir para que el slider vaya de más viejo (izq) a más nuevo (der)
    commits_data = list(reversed(commits_data))

    # Reasignar índices secuenciales tras la inversión
    for idx, entry in enumerate(commits_data):
        entry["index"] = idx

    return {
        "repo_name": repo_name,
        "commits": commits_data
    }

def generate_html(data: dict, output_path: Path):
    repo_name = html.escape(data["repo_name"])
    timeline_json = json.dumps(data["commits"])

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evolution Graph: {repo_name}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0; padding: 0;
            display: flex; flex-direction: column;
            height: 100vh;
            background-color: #f8fafc;
            color: #334155;
            overflow: hidden;
        }}
        
        /* Header */
        .header-bar {{
            height: 60px;
            background: #1e293b; color: white;
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            z-index: 10;
        }}
        .header-title {{ margin: 0; font-size: 1.2rem; }}
        .header-stats {{ font-size: 0.9rem; color: #cbd5e1; display: flex; gap: 15px; align-items: center; }}
        .stat-badge {{ background: #334155; padding: 4px 10px; border-radius: 12px; }}
        
        /* Graph Area */
        #graph-container {{
            flex: 1;
            width: 100%;
            position: relative;
            cursor: grab;
            background: #f1f5f9;
        }}
        #graph-container:active {{ cursor: grabbing; }}
        
        /* Modern Timeline Panel - Floating Island */
        .timeline-panel {{
            position: absolute;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            height: auto;
            padding: 15px 25px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            display: flex; 
            align-items: center;
            gap: 25px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08), 0 4px 6px rgba(0,0,0,0.04);
            border: 1px solid rgba(226, 232, 240, 0.8);
            z-index: 100;
            width: 85%;
            max-width: 900px;
        }}
        
        /* Play Button - Rounded Square */
        .play-btn {{
            background: #3b82f6; color: white;
            border: none; 
            border-radius: 12px; /* Square with rounded corners */
            width: 48px; height: 48px;
            cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: all 0.2s ease;
            box-shadow: 0 4px 10px rgba(59, 130, 246, 0.3);
            flex-shrink: 0;
        }}
        .play-btn:hover {{ background: #2563eb; transform: translateY(-2px); box-shadow: 0 6px 15px rgba(59, 130, 246, 0.4); }}
        .play-btn:active {{ transform: translateY(0); }}
        
        .slider-container {{ flex: 1; display: flex; flex-direction: column; }}
        .commit-labels {{ display: flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 8px; }}
        
        /* Slider Wrapper to hold ticks and track together */
        .slider-wrapper {{
            position: relative;
            width: 100%;
            height: 24px;
            display: flex;
            align-items: center;
        }}

        /* Ticks/Dots */
        .slider-ticks {{
            position: absolute;
            left: 10px; /* Aligns with center of thumb at min */
            right: 10px; /* Aligns with center of thumb at max */
            display: flex;
            justify-content: space-between;
            pointer-events: none;
            z-index: 1;
        }}
        .tick {{
            width: 6px; height: 6px;
            background-color: #cbd5e1;
            border-radius: 50%;
            transition: background-color 0.3s ease;
        }}
        .tick.active {{ background-color: #3b82f6; box-shadow: 0 0 4px rgba(59,130,246,0.5); }}
        
        /* The actual Slider */
        input[type=range] {{
            -webkit-appearance: none; width: 100%; background: transparent;
            position: relative; z-index: 2; margin: 0;
        }}
        input[type=range]:focus {{ outline: none; }}
        input[type=range]::-webkit-slider-thumb {{
            -webkit-appearance: none; 
            height: 20px; width: 20px;
            border-radius: 50%; background: #3b82f6;
            cursor: pointer; border: 3px solid white; 
            box-shadow: 0 2px 6px rgba(0,0,0,0.25);
            margin-top: -7px;
            transition: transform 0.1s;
        }}
        input[type=range]::-webkit-slider-thumb:hover {{ transform: scale(1.15); }}
        input[type=range]::-webkit-slider-runnable-track {{
            width: 100%; height: 6px; cursor: pointer;
            background: #e2e8f0; border-radius: 3px;
        }}
        
        /* Minimalist Commit Info */
        .commit-info {{
            width: auto; min-width: 110px;
            text-align: right;
            padding-left: 15px;
            border-left: 1px solid #e2e8f0;
        }}
        .commit-info span {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        .commit-info strong {{ display: block; color: #0f172a; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 1.1rem; margin-top: 2px; }}

        /* D3 Node Styles */
        .node {{ cursor: pointer; }}
        .node circle {{ stroke: #fff; stroke-width: 2px; }}
        .node text {{ font-size: 12px; font-family: -apple-system, sans-serif; pointer-events: none; }}
        .link {{ fill: none; stroke: #cbd5e1; stroke-width: 2px; transition: stroke 0.5s; }}
        
        /* Animations */
        .node-new rect.main-rect {{ stroke: #10b981 !important; stroke-width: 3px !important; filter: drop-shadow(0 0 6px rgba(16,185,129,0.5)); }}
        .node-removed rect.main-rect {{ stroke: #ef4444 !important; stroke-dasharray: 4,4; opacity: 0.5; }}

        /* Focus Indicator */
        #focus-indicator {{
            display: none;
            align-items: center;
            gap: 8px;
            background: #0f172a;
            border: 1px solid #3b82f6;
            border-radius: 20px;
            padding: 4px 12px;
            font-size: 0.85rem;
            color: #93c5fd;
            animation: focusPulse 2s ease-in-out infinite;
        }}
        #focus-indicator strong {{ color: #e0f2fe; }}
        #focus-indicator .focus-clear-btn {{
            background: #1e3a5f;
            border: none;
            color: #93c5fd;
            border-radius: 10px;
            padding: 2px 8px;
            cursor: pointer;
            font-size: 0.8rem;
        }}
        #focus-indicator .focus-clear-btn:hover {{ background: #2563eb; color: white; }}
        @keyframes focusPulse {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(59,130,246,0.4); }}
            50% {{ box-shadow: 0 0 0 4px rgba(59,130,246,0); }}
        }}
    </style>
</head>
<body>
    <div class="header-bar">
        <h1 class="header-title">Evolution Graph: {repo_name}</h1>
        <div style="display:flex; align-items:center; gap:12px;">
            <div id="focus-indicator">
                <span id="focus-label">Focusing: <strong id="focus-name"></strong></span>
                <button class="focus-clear-btn" onclick="clearFocus()">✕ All</button>
            </div>
            <div class="header-stats" id="header-stats">Loading...</div>
        </div>
    </div>
    
    <div id="graph-container"></div>
    
    <div class="timeline-panel">
        <button class="play-btn" id="play-btn">
            <!-- Icono SVG Moderno para Play -->
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" id="icon-play">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
        </button>
        <div class="slider-container">
            <div class="commit-labels">
                <span>Oldest</span>
                <span style="font-weight: 600; color: #0f172a;" id="current-step-label">Commit 1</span>
                <span>Newest</span>
            </div>
            <div class="slider-wrapper">
                <div class="slider-ticks" id="slider-ticks"></div>
                <input type="range" id="timeline-slider" min="0" value="0" step="1">
            </div>
        </div>
        <div class="commit-info">
            <span>Commit SHA</span>
            <strong id="commit-sha">---</strong>
        </div>
    </div>

    <script>
        const commitsData = {timeline_json};
        const totalCommits = commitsData.length;
        
        // Icons
        const svgPlay = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
        const svgPause = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';

        // Setup UI
        const slider = document.getElementById("timeline-slider");
        slider.max = totalCommits - 1;
        const playBtn = document.getElementById("play-btn");
        const shaDisplay = document.getElementById("commit-sha");
        const stepLabel = document.getElementById("current-step-label");
        const statsDisplay = document.getElementById("header-stats");

        // Generar los "Dots" o Ticks del Slider
        const ticksContainer = document.getElementById("slider-ticks");
        for (let j = 0; j < totalCommits; j++) {{
            let dot = document.createElement("div");
            dot.className = "tick";
            ticksContainer.appendChild(dot);
        }}

        // D3 Setup
        const container = document.getElementById("graph-container");
        const width = container.clientWidth;
        const height = container.clientHeight;

        const svg = d3.select("#graph-container").append("svg")
            .attr("width", width)
            .attr("height", height);
            
        const g = svg.append("g");
        
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => g.attr("transform", event.transform));
        svg.call(zoom);

        // Layout settings
        const dx = 45;  
        const dy = 350; 
        const treeLayout = d3.tree().nodeSize([dx, dy]);
        
        g.append("g").attr("class", "links");
        g.append("g").attr("class", "nodes");
        
        // Center initial view
        svg.call(zoom.transform, d3.zoomIdentity.translate(dy / 2, height / 2).scale(0.8));

        let currentIds = new Set();
        let i = 0;

        // --- Focus State ---
        let activeFocus = null;

        function applyFocus(tree, focus) {{
            if (!focus) return tree;
            const filtered = Object.assign({{}}, tree, {{children: []}});
            if (focus.type === 'category') {{
                const cat = (tree.children || []).find(c => c.name === focus.name);
                if (cat) filtered.children = [cat];
            }} else if (focus.type === 'label') {{
                const cat = (tree.children || []).find(c => c.name === focus.catName);
                if (cat) {{
                    const lbl = (cat.children || []).find(l => l.name === focus.labelName);
                    if (lbl) filtered.children = [Object.assign({{}}, cat, {{children: [lbl]}})];
                }}
            }}
            return filtered;
        }}

        function updateFocusIndicator() {{
            const el = document.getElementById('focus-indicator');
            const labelEl = document.getElementById('focus-label');
            if (!activeFocus) {{
                el.style.display = 'none';
            }} else if (activeFocus.type === 'category') {{
                el.style.display = 'flex';
                labelEl.innerHTML = 'Category: <strong id="focus-name">' + activeFocus.name + '</strong>';
            }} else if (activeFocus.type === 'label') {{
                el.style.display = 'flex';
                labelEl.innerHTML = 'Label: <strong id="focus-name">' + activeFocus.catName + ' › ' + activeFocus.labelName + '</strong>';
            }}
        }}

        function clearFocus() {{
            activeFocus = null;
            updateFocusIndicator();
            updateGraph(parseInt(slider.value));
        }}

        function updateGraph(index) {{
            const commitInfo = commitsData[index];
            shaDisplay.innerText = commitInfo.commit.substring(0, 8);
            stepLabel.innerText = `Commit ${{index + 1}} of ${{totalCommits}}`;
            
            // Actualizar Ticks (Puntos de anclaje de la barra)
            const allTicks = document.querySelectorAll('.tick');
            allTicks.forEach((t, idx) => {{
                if (idx <= index) t.classList.add('active');
                else t.classList.remove('active');
            }});

            const rawData = commitInfo.tree;
            const rootData = applyFocus(rawData, activeFocus);
            const root = d3.hierarchy(rootData);
            
            // Ordenamos alfabéticamente para evitar saltos visuales
            root.sort((a, b) => a.data.name.localeCompare(b.data.name));
            treeLayout(root);

            const nodes = root.descendants();
            const links = root.links();
            
            const numRules = nodes.filter(n => n.data.group === 'rule').length;
            statsDisplay.innerHTML = `
                <span class="stat-badge">Total Nodes: ${{nodes.length - 1}}</span> 
                <span class="stat-badge">Rules: ${{numRules}}</span>
            `;

            const newIds = new Set(nodes.map(d => d.data.id));
            const addedIds = new Set([...newIds].filter(x => !currentIds.has(x) && index > 0));
            currentIds = newIds;

            // --- LINKS ---
            const link = g.select(".links").selectAll("path.link")
                .data(links, d => d.target.data.id);
                
            const linkEnter = link.enter().append("path")
                .attr("class", "link")
                .attr("d", d => {{
                    const o = {{x: d.source.x, y: d.source.y}};
                    return d3.linkHorizontal().x(d => d.y).y(d => d.x)({{source: o, target: o}});
                }})
                .style("opacity", 0);
                
            link.merge(linkEnter).transition().duration(800)
                .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x))
                .style("opacity", 1);
                
            link.exit().transition().duration(500)
                .style("opacity", 0)
                .remove();

            // --- NODES ---
            const node = g.select(".nodes").selectAll("g.node")
                .data(nodes, d => d.data.id);
                
            const nodeEnter = node.enter().append("g")
                .attr("class", "node")
                .attr("transform", d => `translate(${{d.parent ? d.parent.y : d.y}},${{d.parent ? d.parent.x : d.x}})`)
                .style("opacity", 0);
                
            nodeEnter.filter(d => d.data.group !== "root").append("rect")
                .attr("class", "main-rect")
                .attr("width", d => d.data.width || 150)
                .attr("height", 36)
                .attr("y", -18)
                .attr("rx", 6).attr("ry", 6)
                .attr("fill", d => d.data.color)
                .attr("stroke", "#0f172a")
                .attr("stroke-width", 2);
                
            nodeEnter.filter(d => d.data.group === "root")
                .append("image")
                .attr("href", "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23334155' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/></svg>")
                .attr("width", 32).attr("height", 32)
                .attr("x", -16).attr("y", -16);
                
            nodeEnter.append("rect")
                .attr("class", "text-bg")
                .attr("fill", "rgba(255, 255, 255, 0.75)")
                .attr("rx", 3).attr("ry", 3);
                
            nodeEnter.append("text")
                .attr("class", "node-label")
                .attr("dy", d => d.data.group === "root" ? "28px" : "0.31em")
                .attr("x", d => d.data.group === "root" ? 0 : 12)
                .attr("text-anchor", d => d.data.group === "root" ? "middle" : "start")
                .style("fill", "#0f172a").style("font-weight", "500")
                .text(d => d.data.name);

            nodeEnter.append("title")
                .text(d => d.data.raw_text ? d.data.raw_text : d.data.name);

            const nodeUpdate = nodeEnter.merge(node);

            // Click handlers
            nodeUpdate.on("click", (event, d) => {{
                event.stopPropagation();
                if (d.data.group === 'root') {{
                    clearFocus();
                }} else if (d.data.group === 'category') {{
                    activeFocus = {{ type: 'category', name: d.data.name }};
                    updateFocusIndicator();
                    updateGraph(parseInt(slider.value));
                }} else if (d.data.group === 'label') {{
                    const catName = d.parent ? d.parent.data.name : null;
                    if (catName) {{
                        activeFocus = {{ type: 'label', catName: catName, labelName: d.data.name }};
                        updateFocusIndicator();
                        updateGraph(parseInt(slider.value));
                    }}
                }}
            }});
            
            nodeUpdate.select(".node-label").each(function(d) {{
                if (d.data.group === "rule") {{
                    const padding = 24;
                    const maxWidth = (d.data.width || 150) - padding;
                    let textStr = d.data.name;
                    this.textContent = textStr;
                    
                    if (this.getComputedTextLength() > maxWidth && textStr.length > 3) {{
                        let idx = textStr.length;
                        while (this.getComputedTextLength() > maxWidth && idx > 0) {{
                            idx--;
                            this.textContent = textStr.slice(0, idx) + "...";
                        }}
                    }}
                }}
            }});

            nodeUpdate.each(function(d) {{
                const textNode = d3.select(this).select(".node-label").node();
                if (textNode && textNode.getBBox) {{
                    const bbox = textNode.getBBox();
                    if (d.data.group !== "root") {{
                        d3.select(this).select(".text-bg")
                            .attr("x", bbox.x - 4).attr("y", bbox.y - 2)
                            .attr("width", bbox.width + 8).attr("height", bbox.height + 4);
                    }}
                }}
            }});
            
            nodeUpdate.classed("node-new", d => addedIds.has(d.data.id));

            nodeUpdate.transition().duration(800)
                .attr("transform", d => `translate(${{d.y}},${{d.x}})`)
                .style("opacity", 1);
                
            node.exit().transition().duration(500)
                .attr("transform", d => `translate(${{d.parent ? d.parent.y : d.y - 20}},${{d.parent ? d.parent.x : d.x}})`)
                .style("opacity", 0)
                .remove();
        }}

        // Player / Controles
        let playInterval;
        let isPlaying = false;

        function stepNext() {{
            let val = parseInt(slider.value);
            if (val >= totalCommits - 1) {{
                togglePlay(); 
                return;
            }}
            slider.value = val + 1;
            updateGraph(val + 1);
        }}

        function togglePlay() {{
            isPlaying = !isPlaying;
            if (isPlaying) {{
                if (parseInt(slider.value) >= totalCommits - 1) slider.value = 0; 
                playBtn.innerHTML = svgPause;
                updateGraph(parseInt(slider.value));
                playInterval = setInterval(stepNext, 1800); 
            }} else {{
                playBtn.innerHTML = svgPlay;
                clearInterval(playInterval);
            }}
        }}

        playBtn.addEventListener("click", togglePlay);
        
        slider.addEventListener("input", (e) => {{
            if (isPlaying) togglePlay(); 
            updateGraph(parseInt(e.target.value));
        }});

        window.addEventListener("resize", () => {{
            svg.attr("width", container.clientWidth).attr("height", container.clientHeight);
        }});

        if (totalCommits > 0) {{
            updateGraph(0);
        }} else {{
            container.innerHTML = "<h2 style='text-align:center; margin-top: 50px; color: #94a3b8;'>No commits data found.</h2>";
        }}
    </script>
</body>
</html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Evolution Graph visualization successfully generated: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate Interactive Evolution Tree HTML Graph.")
    parser.add_argument("repo_name", type=str, help="Repository folder name in json_trees/migrated_jsons/")
    args = parser.parse_args()

    logger.info(f"Extracting AST data across commits for {args.repo_name}...")
    evolution_data = extract_timeline_data(args.repo_name)
    
    if not evolution_data or not evolution_data["commits"]:
        logger.error("Failed to generate graph. Please check if the repository name is correct and data exists.")
        sys.exit(1)

    root_dir = get_project_root()
    output_dir = root_dir / "dataset" / "evolution_exp" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{args.repo_name}_evolution_graph.html"
    generate_html(evolution_data, output_path)

if __name__ == "__main__":
    main()