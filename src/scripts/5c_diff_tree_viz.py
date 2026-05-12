#!/usr/bin/env python3
import json
import argparse
import logging
import hashlib
import copy
from pathlib import Path
import html
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

# Importamos los modelos de dominio
sys.path.append(str(get_project_root()))
try:
    from src.domain.models import AgentASTDocument
except ImportError as e:
    logger.error(f"FATAL ERROR: Missing dependencies. Details: {e}")
    sys.exit(1)

# ==============================================================================
# 1. GENERACIÓN DE ID ROBUSTO
# Resolvemos la fragilidad del ID de 5a. Normalizamos el texto (sin espacios extra,
# minúsculas, solo alfanuméricos) y tomamos los primeros 40 caracteres.
# ==============================================================================
def get_robust_id(text: str) -> str:
    """Genera un ID único y mucho más estable ante pequeños typos o cambios de formato."""
    if not text:
        return "empty"
    normalized = "".join(c for c in text.lower() if c.isalnum() or c.isspace())
    normalized = " ".join(normalized.split())
    signature = normalized[:40]
    return hashlib.md5(signature.encode('utf-8')).hexdigest()[:10]

def parse_commit_tree(json_data: dict, commit_sha: str, repo_name: str):
    """Parsea el AST y extrae metadatos igual que 5a, pero usando get_robust_id."""
    try:
        doc = AgentASTDocument.model_validate(json_data)
    except Exception as e:
        logger.error(f"Failed to validate JSON for commit {commit_sha}: {e}")
        return None

    tree = {
        "id": "root",
        "name": doc.repo_name,
        "group": "root",
        "color": getattr(doc, 'root_color', "#e2e8f0"),
        "details": getattr(doc, 'root_html_details', ""),
        "children": []
    }
    
    for cat in doc.rootNode.children:
        if getattr(cat, 'count', -1) == 0:
            continue
            
        cat_name = cat.label
        cat_id = f"cat_{cat_name}"
        cat_color = getattr(cat, 'color', "#94a3b8")
        
        cat_node = {
            "id": cat_id, "name": cat_name, "group": "category",
            "color": cat_color, "details": getattr(cat, 'html_details', ""),
            "children": []
        }
        
        for label in cat.children:
            label_name = label.label
            label_id = f"lbl_{cat_name}_{label_name}"
            label_color = getattr(label, 'color', cat_color)
            
            label_node = {
                "id": label_id, "name": label_name, "group": "label",
                "color": label_color, "details": getattr(label, 'html_details', ""),
                "children": []
            }
            
            for rule in label.children:
                text = rule.content.text if (hasattr(rule, 'content') and rule.content) else ""
                rule_label = getattr(rule, 'short_label', None)
                
                if not rule_label or rule_label == "Rule":
                    rule_label = text.strip().split('\n')[0][:60] + "..." if text else "Empty Rule"
                    
                # USAMOS ROBUST ID AQUÍ
                rule_id = f"rule_{cat_name}_{label_name}_{get_robust_id(text)}"
                
                label_node["children"].append({
                    "id": rule_id, "name": rule_label, "group": "rule",
                    "color": label_color, "raw_text": text,
                    "details": getattr(rule, 'html_details', ""),
                    "width": min(max(180, len(rule_label) * 7), 400)
                })
                
            if label_node["children"]: cat_node["children"].append(label_node)
        if cat_node["children"]: tree["children"].append(cat_node)
            
    return tree

# ==============================================================================
# 2. LÓGICA DE DIFF (GHOST NODES)
# ==============================================================================
def get_flat_nodes(tree_node, parent_id=None):
    """Aplana el árbol en un diccionario para búsquedas rápidas."""
    nodes = {tree_node['id']: {'node': tree_node, 'parent_id': parent_id}}
    for child in tree_node.get('children', []):
        nodes.update(get_flat_nodes(child, tree_node['id']))
    return nodes

def mark_deleted_recursively(node):
    """Marca recursivamente un nodo fantasma y todos sus hijos como eliminados."""
    node['diff_status'] = 'deleted'
    for child in node.get('children', []):
        mark_deleted_recursively(child)

def inject_diff_states(prev_tree, curr_tree):
    """Inyecta diferencias entre T-1 y T. Agrega nodos borrados como fantasmas."""
    if not prev_tree:
        curr_nodes = get_flat_nodes(curr_tree)
        for val in curr_nodes.values(): val['node']['diff_status'] = 'kept'
        return curr_tree

    curr_merged = copy.deepcopy(curr_tree)
    prev_nodes = get_flat_nodes(prev_tree)
    curr_nodes = get_flat_nodes(curr_merged)

    # 1. Identificar Nuevos vs Mantenidos
    for nid, val in curr_nodes.items():
        if nid not in prev_nodes:
            val['node']['diff_status'] = 'added'
        else:
            val['node']['diff_status'] = 'kept'

    # 2. Inyectar Eliminados (Ghost Nodes) del paso anterior
    for nid, prev_val in prev_nodes.items():
        if nid not in curr_nodes:
            parent_id = prev_val['parent_id']
            # Si el padre sobrevivió a este commit, le colgamos el fantasma tachado
            if parent_id and parent_id in curr_nodes:
                ghost_node = copy.deepcopy(prev_val['node'])
                mark_deleted_recursively(ghost_node)
                curr_nodes[parent_id]['node'].setdefault('children', []).append(ghost_node)

    return curr_merged

def extract_timeline_data(repo_name: str) -> dict:
    root_dir = get_project_root()
    json_dir = root_dir / "dataset" / "evolution_exp" / "json_trees" / "migrated_jsons" / repo_name
    file_history_path = root_dir / "dataset" / "evolution_exp" / "file_history.json"
    
    if not json_dir.exists(): return None

    commit_order = []
    if file_history_path.exists():
        try:
            history_data = json.loads(file_history_path.read_text(encoding='utf-8'))
            if repo_name in history_data:
                commit_order = [c['sha'] if isinstance(c, dict) else c for c in history_data[repo_name]]
        except Exception: pass

    json_files = list(json_dir.glob("*.json"))
    if not json_files: return None

    if not commit_order:
        json_files.sort(key=lambda x: x.stat().st_mtime)
    else:
        def get_index(filepath):
            sha = filepath.stem
            return commit_order.index(sha) if sha in commit_order else 9999
        json_files.sort(key=get_index)

    raw_commits = []
    for j_path in json_files:
        sha = j_path.stem
        try:
            data = json.loads(j_path.read_text(encoding='utf-8'))
            tree_structure = parse_commit_tree(data, sha, repo_name)
            if tree_structure:
                raw_commits.append({"commit": sha, "tree": tree_structure})
        except Exception as e:
            logger.error(f"Failed to process {j_path.name}: {e}")

    # Orden cronológico (Oldest -> Newest) para procesar el diff correctamente
    raw_commits = list(reversed(raw_commits))

    diff_commits = []
    prev_tree = None
    for idx, entry in enumerate(raw_commits):
        merged_tree = inject_diff_states(prev_tree, entry["tree"])
        diff_commits.append({
            "index": idx,
            "commit": entry["commit"],
            "tree": merged_tree
        })
        # Guardamos el árbol puro actual para comparar en la próxima iteración
        prev_tree = entry["tree"]

    return {"repo_name": repo_name, "commits": diff_commits}

def generate_html(data: dict, output_path: Path):
    repo_name = html.escape(data["repo_name"])
    timeline_json = json.dumps(data["commits"])

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diff Tree Evolution: {repo_name}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 0; display: flex; flex-direction: column;
            height: 100vh; background-color: #f8fafc; color: #334155; overflow: hidden;
        }}
        
        .header-bar {{
            height: 60px; background: #1e293b; color: white; display: flex; align-items: center; 
            justify-content: space-between; padding: 0 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); z-index: 10;
        }}
        .header-title {{ margin: 0; font-size: 1.2rem; }}
        .header-controls-container {{ display: flex; gap: 20px; align-items: center; }}
        .control-group {{
            display: flex; align-items: center; gap: 10px; background: #334155; padding: 6px 14px; 
            border-radius: 8px; font-size: 0.85rem; color: #cbd5e1;
        }}
        .control-group label {{ display: flex; align-items: center; gap: 5px; cursor: pointer; }}
        .control-group input {{ cursor: pointer; accent-color: #3b82f6; }}
        .header-stats {{ font-size: 0.9rem; color: #cbd5e1; display: flex; gap: 10px; }}
        .stat-badge {{ background: #475569; padding: 4px 10px; border-radius: 6px; font-weight: 600; }}
        
        #graph-container {{ flex: 1; width: 100%; position: relative; cursor: grab; background: #f1f5f9; }}
        #graph-container:active {{ cursor: grabbing; }}
        
        #details-panel {{
            position: absolute; top: 80px; right: 20px; width: 320px; max-height: calc(100% - 180px);
            overflow-y: auto; background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(8px);
            border: 1px solid rgba(226, 232, 240, 0.8); border-radius: 12px; padding: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1); display: none; z-index: 200; font-size: 0.95rem; line-height: 1.5;
        }}
        #details-panel h3 {{ margin-top: 0; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }}
        #details-panel .close-btn {{ position: absolute; top: 12px; right: 15px; cursor: pointer; color: #94a3b8; font-weight: bold; }}
        #details-panel .close-btn:hover {{ color: #ef4444; }}

        .timeline-panel {{
            position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
            padding: 15px 25px; background: rgba(255, 255, 255, 0.95); border-radius: 20px;
            display: flex; align-items: center; gap: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.08);
            border: 1px solid rgba(226, 232, 240, 0.8); z-index: 100; width: 85%; max-width: 900px;
        }}
        .play-btn {{
            background: #3b82f6; color: white; border: none; border-radius: 12px; width: 48px; height: 48px; 
            cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }}
        .slider-container {{ flex: 1; display: flex; flex-direction: column; }}
        .commit-labels {{ display: flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 8px; }}
        .slider-wrapper {{ position: relative; width: 100%; height: 24px; display: flex; align-items: center; }}
        input[type=range] {{ -webkit-appearance: none; width: 100%; background: transparent; position: relative; z-index: 2; margin: 0; }}
        input[type=range]::-webkit-slider-thumb {{
            -webkit-appearance: none; height: 20px; width: 20px; border-radius: 50%; background: #3b82f6;
            cursor: pointer; border: 3px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.25); margin-top: -7px;
        }}
        input[type=range]::-webkit-slider-runnable-track {{ width: 100%; height: 6px; cursor: pointer; background: #e2e8f0; border-radius: 3px; }}
        
        .commit-info {{ width: auto; min-width: 110px; text-align: right; padding-left: 15px; border-left: 1px solid #e2e8f0; }}
        .commit-info span {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; }}
        .commit-info strong {{ display: block; color: #0f172a; font-family: monospace; font-size: 1.1rem; }}

        /* D3 Nodes Base Styles */
        .node {{ cursor: pointer; }}
        .node text {{ font-size: 12px; font-family: -apple-system, sans-serif; pointer-events: none; }}
        .link {{ fill: none; stroke-width: 2px; transition: all 0.5s; }}
        
        /* DIFF STATUS CLASSES */
        /* Nodos Nuevos (Añadidos) */
        .node-added rect.main-rect {{ 
            stroke: #10b981 !important; stroke-width: 3px !important; 
            filter: drop-shadow(0 0 6px rgba(16,185,129,0.5)); 
        }}
        /* Nodos Fantasma (Borrados) */
        .node-deleted rect.main-rect {{ 
            stroke: #ef4444 !important; stroke-width: 2px !important; stroke-dasharray: 4,4;
            fill: #cbd5e1 !important; /* fondo oscurecido */
        }}
        .node-deleted .text-bg {{ fill: rgba(226, 232, 240, 0.9) !important; }}
        .node-deleted text.node-label {{ 
            text-decoration: line-through; fill: #64748b !important; font-style: italic;
        }}

        #focus-indicator {{
            display: none; align-items: center; gap: 8px; background: #0f172a; border: 1px solid #3b82f6; 
            border-radius: 8px; padding: 4px 12px; font-size: 0.85rem; color: #93c5fd;
        }}
        #focus-indicator .focus-clear-btn {{
            background: #1e3a5f; border: none; color: #93c5fd; border-radius: 6px; padding: 2px 8px; cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="header-bar">
        <h1 class="header-title">Diff Tree: {repo_name}</h1>
        <div class="header-controls-container">
            <div id="focus-indicator">
                <span id="focus-label">Focusing: <strong id="focus-name"></strong></span>
                <button class="focus-clear-btn" onclick="clearFocus()">✕ Clear</button>
            </div>
            
            <div class="control-group">
                <label><input type="radio" name="interaction-mode" value="focus" checked> Filter/Focus Mode</label>
                <label style="border-left: 1px solid #64748b; padding-left: 10px; margin-left: 5px;">
                    <input type="radio" name="interaction-mode" value="inspect"> Inspect Details Mode
                </label>
            </div>
            <div class="control-group">
                <label><input type="checkbox" id="auto-fit-toggle" checked> Auto-Fit Zoom</label>
            </div>
            <div class="header-stats" id="header-stats">Loading...</div>
        </div>
    </div>
    
    <div id="graph-container"></div>

    <div id="details-panel">
        <span class="close-btn" onclick="document.getElementById('details-panel').style.display='none'">✕</span>
        <h3>Node Details</h3>
        <div id="details-content"></div>
    </div>
    
    <div class="timeline-panel">
        <button class="play-btn" id="play-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" id="icon-play"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        </button>
        <div class="slider-container">
            <div class="commit-labels">
                <span>Oldest</span>
                <span style="font-weight: 600; color: #0f172a;" id="current-step-label">Commit 1</span>
                <span>Newest</span>
            </div>
            <div class="slider-wrapper">
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
        
        const slider = document.getElementById("timeline-slider");
        slider.max = totalCommits - 1;
        const playBtn = document.getElementById("play-btn");
        
        const container = document.getElementById("graph-container");
        let width = container.clientWidth;
        let height = container.clientHeight;

        const svg = d3.select("#graph-container").append("svg").attr("width", width).attr("height", height);
        const g = svg.append("g");
        
        const zoom = d3.zoom().scaleExtent([0.1, 4]).on("zoom", (e) => g.attr("transform", e.transform));
        svg.call(zoom);

        svg.on("click", () => document.getElementById("details-panel").style.display = "none");

        const treeLayout = d3.tree().nodeSize([45, 350]);
        g.append("g").attr("class", "links");
        g.append("g").attr("class", "nodes");
        
        let activeFocus = null;
        let collapsedNodes = new Set();

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

        function clearFocus() {{
            activeFocus = null;
            document.getElementById('focus-indicator').style.display = 'none';
            updateGraph(parseInt(slider.value));
        }}

        function showDetails(nodeData) {{
            const panel = document.getElementById("details-panel");
            const content = document.getElementById("details-content");
            let html = `<strong>Type: ${{nodeData.group.toUpperCase()}}</strong><br>`;
            
            if (nodeData.diff_status === 'deleted') {{
                html += `<div style="background:#fef2f2; border:1px solid #fca5a5; color:#ef4444; padding:8px; border-radius:6px; margin: 10px 0; font-weight:bold; font-size:0.85rem;">⚠️ Ghost Node: This node was deleted in this commit.</div>`;
            }}

            if (nodeData.details) html += `<div style="margin-top:10px;">${{nodeData.details}}</div>`;
            if (nodeData.raw_text) {{
                html += `<hr style="border:0; border-top:1px solid #e2e8f0; margin:15px 0;">
                         <strong>Raw Content:</strong>
                         <pre style="white-space:pre-wrap; font-family:monospace; font-size:0.85rem; background:#f8fafc; padding:10px; border-radius:6px; border:1px solid #e2e8f0;">${{nodeData.raw_text}}</pre>`;
            }}
            content.innerHTML = html;
            panel.style.display = "block";
        }}

        function autoFitGraph(nodes) {{
            if (!document.getElementById("auto-fit-toggle").checked || nodes.length === 0) return;
            
            let minX = Infinity, maxX = -Infinity;
            let minY = Infinity, maxY = -Infinity; 
            
            nodes.forEach(n => {{
                if (n.x < minX) minX = n.x; 
                if (n.x > maxX) maxX = n.x;
                if (n.y < minY) minY = n.y; 
                if (n.y + (n.data.width||200) > maxY) maxY = n.y + (n.data.width||200);
            }});

            // Calculamos el tamaño real del árbol
            const treeHeight = (maxX - minX); 
            const treeWidth = (maxY - minY);  

            // Definimos el área segura (mucha reserva abajo para el panel timeline)
            const marginTop = 40;
            const marginBottom = 180; // Aumentado para evitar colisiones
            const marginLeft = 40;
            const marginRight = 40;

            const availableW = width - marginLeft - marginRight;
            const availableH = height - marginTop - marginBottom;

            // Calculamos la escala necesaria
            const scale = Math.min(availableW / (treeWidth || 1), availableH / (treeHeight || 1), 1.1); 

            // Desplazamos el centro visual teniendo en cuenta el área segura disponible
            const tx = width / 2 - (minY + treeWidth / 2) * scale;
            const ty = marginTop + (availableH / 2) - (minX + treeHeight / 2) * scale;

            svg.transition().duration(800)
               .call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
        }}

        function updateGraph(index) {{
            const commitInfo = commitsData[index];
            document.getElementById("commit-sha").innerText = commitInfo.commit.substring(0, 8);
            document.getElementById("current-step-label").innerText = `Commit ${{index + 1}} of ${{totalCommits}}`;

            const rawData = commitInfo.tree;
            const rootData = applyFocus(rawData, activeFocus);
            const root = d3.hierarchy(rootData);
            
            root.each(d => {{
                if (collapsedNodes.has(d.data.id) && d.children) {{
                    d._children = d.children; d.children = null;
                }}
            }});

            root.sort((a, b) => a.data.name.localeCompare(b.data.name));
            treeLayout(root);

            const nodes = root.descendants();
            const links = root.links();
            
            const numRules = nodes.filter(n => n.data.group === 'rule').length;
            const numDeleted = nodes.filter(n => n.data.diff_status === 'deleted').length;
            document.getElementById("header-stats").innerHTML = `
                <span class="stat-badge">Visible Nodes: ${{nodes.length - 1}}</span> 
                <span class="stat-badge">Visible Rules: ${{numRules}}</span>
                ${{numDeleted > 0 ? `<span class="stat-badge" style="background:#ef4444">Ghosts: ${{numDeleted}}</span>` : ''}}
            `;

            autoFitGraph(nodes);

            // --- LINKS ---
            const link = g.select(".links").selectAll("path.link").data(links, d => d.target.data.id);
            const linkEnter = link.enter().append("path").attr("class", "link")
                .attr("d", d => {{
                    const o = {{x: d.source.x, y: d.source.y}};
                    return d3.linkHorizontal().x(d => d.y).y(d => d.x)({{source: o, target: o}});
                }}).style("opacity", 0);
                
            link.merge(linkEnter).transition().duration(800)
                .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x))
                .style("opacity", d => d.target.data.diff_status === 'deleted' ? 0.4 : 1)
                .attr("stroke", d => d.target.data.diff_status === 'deleted' ? "#ef4444" : "#cbd5e1")
                .style("stroke-dasharray", d => d.target.data.diff_status === 'deleted' ? "5,5" : "none");
                
            link.exit().transition().duration(500).style("opacity", 0).remove();

            // --- NODES ---
            const node = g.select(".nodes").selectAll("g.node").data(nodes, d => d.data.id);
            const nodeEnter = node.enter().append("g").attr("class", "node")
                .attr("transform", d => `translate(${{d.parent ? d.parent.y : d.y}},${{d.parent ? d.parent.x : d.x}})`)
                .style("opacity", 0);
                
            nodeEnter.filter(d => d.data.group !== "root").append("rect")
                .attr("class", "main-rect")
                .attr("height", 36).attr("y", -18).attr("rx", 6).attr("ry", 6)
                .attr("fill", d => d.data.color).attr("stroke", "#0f172a").attr("stroke-width", 2);
                
            nodeEnter.filter(d => d.data.group === "root").append("image")
                .attr("href", "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23334155' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/></svg>")
                .attr("width", 32).attr("height", 32).attr("x", -16).attr("y", -16);
                
            nodeEnter.append("rect").attr("class", "text-bg").attr("fill", "rgba(255, 255, 255, 0.75)").attr("rx", 3);
            nodeEnter.append("text").attr("class", "node-label")
                .attr("dy", d => d.data.group === "root" ? "28px" : "0.31em")
                .attr("x", d => d.data.group === "root" ? 0 : 12)
                .attr("text-anchor", d => d.data.group === "root" ? "middle" : "start")
                .style("fill", "#0f172a").style("font-weight", "500");

            const nodeUpdate = nodeEnter.merge(node);
            
            // APLICAR CLASES DIFF (AÑADIDOS Y ELIMINADOS)
            nodeUpdate.attr("class", d => {{
                let cls = "node";
                if(d.data.diff_status === 'added' && index > 0) cls += " node-added";
                if(d.data.diff_status === 'deleted') cls += " node-deleted";
                return cls;
            }});

            nodeUpdate.on("click", (event, d) => {{
                event.stopPropagation();
                const mode = document.querySelector('input[name="interaction-mode"]:checked').value;
                if (mode === 'focus') {{
                    document.getElementById("details-panel").style.display = "none";
                    if (d.data.group === 'root') clearFocus();
                    else if (d.data.group === 'category' || d.data.group === 'label') {{
                        activeFocus = d.data.group === 'category' ? 
                            {{ type: 'category', name: d.data.name }} : 
                            {{ type: 'label', catName: d.parent.data.name, labelName: d.data.name }};
                        const ind = document.getElementById('focus-indicator');
                        ind.style.display = 'flex';
                        document.getElementById('focus-name').innerText = d.data.name;
                        updateGraph(parseInt(slider.value));
                    }}
                }} else {{
                    showDetails(d.data);
                    if (d.data.group !== 'root' && d.data.group !== 'rule') {{
                        collapsedNodes.has(d.data.id) ? collapsedNodes.delete(d.data.id) : collapsedNodes.add(d.data.id);
                        updateGraph(parseInt(slider.value));
                    }}
                }}
            }});
            
            nodeUpdate.select(".main-rect").attr("width", d => d.data.width || 150);
            
            nodeUpdate.select(".node-label").each(function(d) {{
                let textStr = d.data.name;
                if (d.data.group === "rule") {{
                    const maxW = (d.data.width || 150) - 24;
                    this.textContent = textStr;
                    if (this.getComputedTextLength() > maxW && textStr.length > 3) {{
                        let idx = textStr.length;
                        while (this.getComputedTextLength() > maxW && idx > 0) {{
                            idx--; this.textContent = textStr.slice(0, idx) + "...";
                        }}
                    }}
                }} else this.textContent = textStr;
            }});

            nodeUpdate.each(function(d) {{
                const tNode = d3.select(this).select(".node-label").node();
                if (tNode && tNode.getBBox && d.data.group !== "root") {{
                    const bbox = tNode.getBBox();
                    d3.select(this).select(".text-bg").attr("x", bbox.x - 4).attr("y", bbox.y - 2)
                        .attr("width", bbox.width + 8).attr("height", bbox.height + 4);
                }}
            }});
            
            nodeUpdate.select(".main-rect")
                .attr("stroke-dasharray", d => d._children ? "4,4" : (d.data.diff_status==='deleted' ? "4,4" : "none"))
                .attr("stroke-width", d => d._children ? 3 : 2);

            nodeUpdate.transition().duration(800)
                .attr("transform", d => `translate(${{d.y}},${{d.x}})`)
                .style("opacity", 1);
                
            node.exit().transition().duration(500)
                .attr("transform", d => `translate(${{d.parent ? d.parent.y : d.y - 20}},${{d.parent ? d.parent.x : d.x}})`)
                .style("opacity", 0).remove();
        }}

        let playInterval, isPlaying = false;
        function togglePlay() {{
            isPlaying = !isPlaying;
            if (isPlaying) {{
                if (parseInt(slider.value) >= totalCommits - 1) slider.value = 0; 
                document.getElementById("play-btn").innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
                updateGraph(parseInt(slider.value));
                playInterval = setInterval(() => {{
                    let val = parseInt(slider.value);
                    if (val >= totalCommits - 1) {{ togglePlay(); return; }}
                    slider.value = val + 1; updateGraph(val + 1);
                }}, 1800); 
            }} else {{
                document.getElementById("play-btn").innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
                clearInterval(playInterval);
            }}
        }}

        document.getElementById("play-btn").addEventListener("click", togglePlay);
        slider.addEventListener("input", (e) => {{
            if (isPlaying) togglePlay(); 
            updateGraph(parseInt(e.target.value));
        }});

        window.addEventListener("resize", () => {{
            width = container.clientWidth; height = container.clientHeight;
            svg.attr("width", width).attr("height", height);
            if (totalCommits > 0) updateGraph(parseInt(slider.value));
        }});

        if (totalCommits > 0) updateGraph(0);
        else container.innerHTML = "<h2 style='text-align:center; margin-top: 50px;'>No commits data found.</h2>";
    </script>
</body>
</html>
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Diff Evolution Graph successfully generated: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate Interactive Diff Evolution Tree.")
    parser.add_argument("repo_name", type=str)
    args = parser.parse_args()

    evolution_data = extract_timeline_data(args.repo_name)
    if not evolution_data or not evolution_data["commits"]:
        logger.error("Failed to generate graph.")
        sys.exit(1)

    out_dir = get_project_root() / "dataset" / "evolution_exp" / "visualizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    generate_html(evolution_data, out_dir / f"{args.repo_name}_5c_diff_tree.html")

if __name__ == "__main__":
    main()