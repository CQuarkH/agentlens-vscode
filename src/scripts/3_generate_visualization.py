#!/usr/bin/env python3
import json
import argparse
import logging
from pathlib import Path
import html

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

import sys
# Add src parent to the python path so imports resolve
sys.path.append(str(get_project_root()))
from src.domain.models import AgentASTDocument

def escape(text):
    if not text:
        return ""
    return html.escape(str(text))

def build_graph_data(doc: AgentASTDocument):
    """Converts the Domain AST Model into a flat list of nodes and links for D3.js"""
    nodes = []
    links = []
    
    # Add Root Node (Level 0)
    nodes.append({
        "id": "root",
        "group": "root",
        "label": doc.repo_name,
        "radius": doc.force_graph_root_radius,
        "color": doc.root_color,
        "details": doc.root_html_details
    })
    
    for cat in doc.rootNode.children:
        if cat.count == 0:
            continue
            
        # Add Category Node (Level 1)
        nodes.append({
            "id": cat.id,
            "group": "category",
            "label": cat.label,
            "radius": cat.force_graph_radius,
            "color": cat.color,
            "details": cat.html_details
        })
        
        # Link Root -> Category
        links.append({
            "source": "root",
            "target": cat.id,
            "value": 3
        })
        
        # Add Rule Nodes (Level 2)
        for rule in cat.children:
            nodes.append({
                "id": rule.graph_id,
                "group": "rule",
                "label": rule.short_label,
                "radius": rule.force_graph_radius,
                "color": rule.color,
                "details": rule.html_details,
                "strength": rule.metadata.strength
            })
            
            # Link Category -> Rule
            links.append({
                "source": cat.id,
                "target": rule.graph_id,
                "value": 1
            })
            
    return json.dumps({"nodes": nodes, "links": links})

def generate_html(md_content, doc: AgentASTDocument, output_path):
    repo_name = escape(doc.repo_name)
    md_source = escape(doc.source_file)
    escaped_md = escape(md_content)
    
    # Transform Domain AST to D3 Hierarchical JSON
    graph_json_str = build_graph_data(doc)

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AST Graph View: {repo_name}</title>
    <!-- Include D3.js -->
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
            flex: 0 0 35%; /* Fixed width for text */
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
            flex: 1; /* Graph gets remaining space */
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
        
        /* Node Details Sidebar inside the Graph Pane */
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
        
        /* D3 Elements */
        .node-label {{
            font-family: sans-serif;
            font-size: 10px;
            pointer-events: none;
            fill: #334155;
            text-shadow: 1px 1px 0 #fff, -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff;
        }}
        .node-label.rule-label {{ display: none; }} /* Hide rule labels by default to prevent clutter */
        g.node:hover .node-label.rule-label {{ display: block; }} /* Show on hover */
        
        g.node circle {{
            stroke: #fff;
            stroke-width: 1.5px;
            cursor: pointer;
            transition: stroke-width 0.2s;
        }}
        g.node:hover circle {{ stroke-width: 3px; stroke: #334155; }}
        
        .link {{
            stroke: #cbd5e1;
            stroke-opacity: 0.6;
        }}
        
        /* Legend */
        .legend {{
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
        <h1 class="header-title">{repo_name} - Cognitive Load Reduction View V1 (Graph)</h1>
    </div>
    
    <div class="split-container">
        <!-- RAW MARKDOWN PANE -->
        <div class="left-pane">
            <h2 style="font-size: 1.1rem; text-transform: uppercase; color: #64748b; margin-top: 0; padding-bottom: 10px; border-bottom: 1px solid #e2e8f0; margin-bottom: 20px; font-family: sans-serif;">Raw Document ({md_source})</h2>
            {escaped_md}
        </div>
        
        <!-- INTERACTIVE AST GRAPH PANE -->
        <div class="right-pane">
            <h2 class="pane-title">Interactive AST Graph</h2>
            
            <div id="graph-container"></div>
            
            <div id="details-panel">
                <span class="close-btn" onclick="document.getElementById('details-panel').style.display='none'">✕</span>
                <h3>Node Details</h3>
                <div id="details-content">Click a node to view its structural properties and rules.</div>
            </div>
            
            <div class="legend">
                <strong>Node Types</strong>
                <div class="legend-item"><div class="legend-color" style="background: #1e293b;"></div> Repository (Root)</div>
                <div class="legend-item"><div class="legend-color" style="background: #60a5fa;"></div> Category</div>
                <div class="legend-item"><div class="legend-color" style="background: #ef4444;"></div> MUST Rule</div>
                <div class="legend-item"><div class="legend-color" style="background: #eab308;"></div> SHOULD Rule</div>
                <br>
                <small><em>Hint: Scroll to zoom, drag to pan.<br>Hover rules to read, click to inspect.</em></small>
            </div>
        </div>
    </div>

    <!-- D3.js Graph Rendering Script -->
    <script>
        const graphData = {graph_json_str};

        const container = document.getElementById("graph-container");
        const width = container.clientWidth;
        const height = container.clientHeight;

        // Initialize SVG
        const svg = d3.select("#graph-container")
            .append("svg")
            .attr("width", width)
            .attr("height", height);
            
        // Zoom functionality
        const g = svg.append("g");
        
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
            
        svg.call(zoom);
        
        // Setup Force Simulation
        // Pushes nodes apart, links pull them together, centers them in the view
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(d => d.source.group === 'root' ? 150 : 80))
            .force("charge", d3.forceManyBody().strength(d => d.group === 'root' ? -1000 : (d.group === 'category' ? -500 : -100)))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide().radius(d => d.radius + 5).iterations(2));

        // Draw Links
        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(graphData.links)
            .join("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.sqrt(d.value));

        // Draw Nodes
        const node = g.append("g")
            .attr("class", "nodes")
            .selectAll("g")
            .data(graphData.nodes)
            .join("g")
            .attr("class", "node")
            .call(drag(simulation));

        // Node Circles
        node.append("circle")
            .attr("r", d => d.radius)
            .attr("fill", d => d.color)
            .on("click", (event, d) => showDetails(d));

        // Node Labels (Only for root and categories by default)
        node.append("text")
            .attr("class", d => d.group === 'rule' ? "node-label rule-label" : "node-label")
            .attr("dx", d => d.radius + 5)
            .attr("dy", 4)
            .text(d => d.group === 'root' ? '' : d.label); // Root label is usually too big, skip it
            
        node.filter(d => d.group === 'root').append("text")
             .attr("class", "node-label")
             .attr("text-anchor", "middle")
             .attr("dy", d => -d.radius - 8)
             .style("font-size", "14px")
             .style("font-weight", "bold")
             .text(d => d.label);

        // Simulation Tick Update
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});

        // Drag Behavior Functions
        function drag(simulation) {{
            function dragstarted(event) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }}
            function dragged(event) {{
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }}
            function dragended(event) {{
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }}
            return d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended);
        }}
        
        // Details Panel Function
        function showDetails(nodeData) {{
            const panel = document.getElementById("details-panel");
            const content = document.getElementById("details-content");
            
            let html = `<strong>${{nodeData.group.toUpperCase()}}</strong><br>`;
            html += nodeData.details;
            
            content.innerHTML = html;
            panel.style.display = "block";
            
            // Highlight clicked node
            node.selectAll("circle").style("stroke", "#fff").style("stroke-width", "1.5px");
            d3.select(event.currentTarget).style("stroke", "#0f172a").style("stroke-width", "3px");
        }}
        
        // Handle window resize
        window.addEventListener("resize", () => {{
            const newWidth = container.clientWidth;
            const newHeight = container.clientHeight;
            svg.attr("width", newWidth).attr("height", newHeight);
            simulation.force("center", d3.forceCenter(newWidth / 2, newHeight / 2));
            simulation.alpha(0.3).restart();
        }});
    </script>
</body>
</html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Successfully generated visualization: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate Interactive D3 HTML Graph from Phase 2 AST.")
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
    # Looking for markdown both in the original cache and the experimental folder just in case
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
    
    output_path = output_dir / f"{json_path.stem}_viz.html"
    generate_html(md_content, doc, output_path)

if __name__ == "__main__":
    main()
