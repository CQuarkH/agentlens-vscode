let evoSvg = null;
let evoG = null;
let evoZoom = null;
let evoSlider = null;
let evoCommitsData = [];
let evoTotalCommits = 0;
let evoActiveFocus = null;
let evoCollapsedNodes = new Set();
let evoSelectedNodeId = null;

let deltaPlayheadLine = null;
let deltaChartXScale = null;
let deltaChartTarget = null;

function togglePanel(panel, headerEl) {
  const body = panel.querySelector(".delta-body, .legend-body");
  const icon = headerEl ? headerEl.querySelector(".toggle-icon") : panel.querySelector(".toggle-icon");
  if (!body) return;
  const isCollapsed = panel.getAttribute("data-collapsed") === "true";
  if (isCollapsed) {
    panel.setAttribute("data-collapsed", "false");
    body.style.display = "";
    panel.style.width = panel.getAttribute("data-ew") || "";
    panel.style.padding = "";
    panel.style.borderRadius = "";
    panel.style.cursor = "";
    if (icon) icon.innerHTML = "&#9660;";
  } else {
    panel.setAttribute("data-collapsed", "true");
    panel.setAttribute("data-ew", panel.style.width || "");
    body.style.display = "none";
    panel.style.width = "auto";
    panel.style.padding = "6px 16px";
    panel.style.borderRadius = "24px";
    panel.style.cursor = "pointer";
    if (icon) icon.innerHTML = "&#9654;";
  }
}

function renderEvolution(data) {
  const container = document.getElementById("evolution-graph-container");
  container.innerHTML = "";

  evoCommitsData = data.commits || [];
  evoTotalCommits = evoCommitsData.length;

  if (evoTotalCommits === 0) {
    container.innerHTML = '<p class="placeholder-text">No commit data available.</p>';
    return;
  }

  const width = container.clientWidth;
  const height = container.clientHeight;

  /* HEADER BAR - Light mode */
  const header = document.createElement("div");
  header.className = "evolution-header";
  header.style.cssText = "display:flex;align-items:center;gap:10px;padding:6px 14px;background:#ffffff;border-bottom:1px solid #e2e8f0;flex-shrink:0;";
  header.innerHTML = `
    <div id="focus-indicator" style="display:none;align-items:center;gap:6px;background:#eff6ff;border:1px solid #93c5fd;border-radius:6px;padding:3px 10px;font-size:0.8rem;color:#1e40af;">
      <span>Focus: <strong id="focus-name"></strong></span>
      <button onclick="window.clearEvoFocus()" style="background:#dbeafe;border:none;color:#1e40af;border-radius:4px;padding:1px 6px;cursor:pointer;font-size:0.75rem;">&#10005;</button>
    </div>
    <div style="display:flex;align-items:center;gap:6px;background:#f1f5f9;padding:3px 10px;border-radius:6px;font-size:0.8rem;color:#334155;">
      <label><input type="radio" name="evo-interaction-mode" value="focus" checked> Filter</label>
      <label style="border-left:1px solid #cbd5e1;padding-left:8px;margin-left:4px;">
        <input type="radio" name="evo-interaction-mode" value="inspect"> Inspect
      </label>
    </div>
    <div style="display:flex;align-items:center;gap:6px;background:#f1f5f9;padding:3px 10px;border-radius:6px;font-size:0.8rem;color:#334155;">
      <label><input type="checkbox" id="evo-auto-fit" checked> Auto-Fit</label>
    </div>
    <div id="evo-header-stats" style="font-size:0.8rem;color:#475569;display:flex;gap:8px;margin-left:auto;">
      <span style="background:#e2e8f0;padding:2px 8px;border-radius:4px;font-weight:600;">Nodes: 0</span>
      <span style="background:#e2e8f0;padding:2px 8px;border-radius:4px;font-weight:600;">Rules: 0</span>
    </div>
  `;
  container.parentElement.insertBefore(header, container);

  /* DELTA CHART PANEL - Collapsible */
  const deltaPanel = document.createElement("div");
  deltaPanel.className = "delta-chart-panel";
  deltaPanel.style.cssText = "position:absolute;top:60px;right:20px;background:rgba(255,255,255,0.95);border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.08);z-index:100;width:340px;display:flex;flex-direction:column;";
  deltaPanel.innerHTML = `
    <div class="delta-header" style="display:flex;justify-content:space-between;align-items:center;padding:10px 15px 5px 15px;cursor:pointer;" onclick="togglePanel(this.parentElement, this)">
      <h4 style="margin:0;font-size:0.85rem;color:#0f172a;text-transform:uppercase;display:flex;align-items:center;gap:6px;">
        <span style="font-size:0.7rem;color:#94a3b8;" class="toggle-icon">&#9660;</span>
        Added vs Deleted
      </h4>
      <div style="display:flex;align-items:center;gap:6px;">
        <span id="delta-focus-title" style="background:#e0f2fe;color:#0284c7;padding:2px 6px;border-radius:4px;font-size:0.65rem;font-weight:700;">Global</span>
        <span style="font-size:0.7rem;color:#94a3b8;cursor:pointer;" onclick="event.stopPropagation(); togglePanel(this.parentElement.parentElement.parentElement, this.parentElement.parentElement.querySelector('.delta-header'));">&#10005;</span>
      </div>
    </div>
    <div class="delta-body" style="padding:0 15px 12px 15px;">
      <div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:5px;color:#64748b;">
        <div style="display:flex;align-items:center;gap:4px;">
          <span style="width:8px;height:8px;background:#10b981;display:inline-block;border-radius:2px;"></span>
          Added: <strong id="leg-added">0</strong>
        </div>
        <div style="display:flex;align-items:center;gap:4px;">
          <span style="width:8px;height:8px;background:#ef4444;display:inline-block;border-radius:2px;"></span>
          Deleted: <strong id="leg-deleted">0</strong>
        </div>
      </div>
      <div id="mini-delta-chart" style="width:100%;height:220px;position:relative;"></div>
    </div>
  `;
  container.appendChild(deltaPanel);

  /* LEGEND PANEL - Collapsible */
  const legendPanel = document.createElement("div");
  legendPanel.className = "legend-panel";
  legendPanel.style.cssText = "position:absolute;top:60px;left:20px;background:rgba(255,255,255,0.95);border:1px solid #e2e8f0;border-radius:8px;box-shadow:0 4px 15px rgba(0,0,0,0.05);z-index:100;font-size:0.8rem;color:#475569;";
  legendPanel.innerHTML = `
    <div class="legend-header" style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px 4px 12px;cursor:pointer;" onclick="togglePanel(this.parentElement, this)">
      <h4 style="margin:0;font-size:0.85rem;color:#0f172a;text-transform:uppercase;display:flex;align-items:center;gap:6px;">
        <span style="font-size:0.7rem;color:#94a3b8;" class="toggle-icon">&#9660;</span>
        Metrics
      </h4>
    </div>
    <div class="legend-body" style="padding:0 12px 10px 12px;">
      <div style="display:grid;grid-template-columns:auto auto;gap:6px 14px;">
        <div><span style="font-size:0.65rem;font-weight:bold;padding:1px 3px;border-radius:2px;font-family:monospace;border:1px solid;background:#dbeafe;color:#1e40af;border-color:#bfdbfe;">LBL</span> Labels</div>
        <div><span style="font-size:0.65rem;font-weight:bold;padding:1px 3px;border-radius:2px;font-family:monospace;border:1px solid;background:#d1fae5;color:#065f46;border-color:#a7f3d0;">RUL</span> Rules</div>
        <div><span style="font-size:0.65rem;font-weight:bold;padding:1px 3px;border-radius:2px;font-family:monospace;border:1px solid;background:#f3e8ff;color:#6b21a8;border-color:#e9d5ff;">COD</span> Code Ratio</div>
        <div><span style="font-size:0.65rem;font-weight:bold;padding:1px 3px;border-radius:2px;font-family:monospace;border:1px solid;background:#ffedd5;color:#9a3412;border-color:#fed7aa;">FRE</span> Readability</div>
        <div><span style="font-size:0.65rem;font-weight:bold;padding:1px 3px;border-radius:2px;font-family:monospace;border:1px solid;background:#f1f5f9;color:#475569;border-color:#cbd5e1;">LEN</span> Length</div>
        <div><span style="font-size:0.65rem;font-weight:bold;padding:1px 3px;border-radius:2px;font-family:monospace;border:1px solid;background:#fef2f2;color:#991b1b;border-color:#fecaca;">SYM</span> Symbols</div>
      </div>
    </div>
  `;
  container.appendChild(legendPanel);

  /* TIMELINE PANEL */
  const timelinePanel = document.createElement("div");
  timelinePanel.className = "timeline-panel";
  timelinePanel.style.cssText = "position:absolute;bottom:30px;left:50%;transform:translateX(-50%);padding:15px 25px;background:rgba(255,255,255,0.95);border-radius:20px;display:flex;align-items:center;gap:25px;box-shadow:0 10px 25px rgba(0,0,0,0.08);border:1px solid rgba(226,232,240,0.8);z-index:100;width:85%;max-width:900px;";
  timelinePanel.innerHTML = `
    <button class="play-btn" id="evo-play-btn" style="background:#3b82f6;color:white;border:none;border-radius:12px;width:48px;height:48px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
    </button>
    <div class="slider-container" style="flex:1;display:flex;flex-direction:column;">
      <div class="commit-labels" style="display:flex;justify-content:space-between;font-size:0.8rem;color:#64748b;margin-bottom:8px;">
        <span>Oldest</span>
        <span style="font-weight:600;color:#0f172a;" id="evo-current-step">Commit 1</span>
        <span>Newest</span>
      </div>
      <div class="slider-wrapper">
        <input type="range" id="evo-slider" min="0" value="0" step="1" max="${evoTotalCommits - 1}" style="-webkit-appearance:none;width:100%;background:transparent;position:relative;z-index:2;margin:0;">
      </div>
    </div>
    <div class="commit-info" style="width:auto;min-width:110px;text-align:right;padding-left:15px;border-left:1px solid #e2e8f0;">
      <span style="color:#64748b;font-size:0.75rem;text-transform:uppercase;">SHA</span>
      <strong id="evo-commit-sha" style="display:block;color:#0f172a;font-family:monospace;font-size:1.1rem;">---</strong>
    </div>
  `;
  container.appendChild(timelinePanel);

  evoSvg = d3.select("#evolution-graph-container").append("svg").attr("width", width).attr("height", height);
  evoG = evoSvg.append("g");

  evoZoom = d3.zoom().scaleExtent([0.1, 4]).on("zoom", (e) => evoG.attr("transform", e.transform));
  evoSvg.call(evoZoom);
  evoSvg.on("click", () => {
    document.getElementById("details-panel").style.display = "none";
    evoSelectedNodeId = null;
    console.log("[AgentLens] evo bg clearHighlight");
    if (typeof vscode !== "undefined") vscode.postMessage({ command: "clearHighlight" });
  });

  const treeLayout = d3.tree().nodeSize([160, 350]);
  evoG.append("g").attr("class", "links");
  evoG.append("g").attr("class", "nodes");

  evoSlider = document.getElementById("evo-slider");

  /* DELTA CHART */
  function renderDeltaChart(targetName) {
    deltaChartTarget = targetName;
    const panel = document.getElementById("mini-delta-chart");
    panel.innerHTML = "";

    const deltaData = evoCommitsData.map(d => {
      if (targetName === "global") {
        return { idx: d.index, added: d.stats.delta.global.added, deleted: d.stats.delta.global.deleted };
      } else {
        const catStats = (d.stats.delta.by_category && d.stats.delta.by_category[targetName]) || { added: 0, deleted: 0 };
        return { idx: d.index, added: catStats.added, deleted: catStats.deleted };
      }
    });

    const badge = document.getElementById("delta-focus-title");
    if (targetName === "global") {
      badge.innerText = "Global"; badge.style.background = "#e0f2fe"; badge.style.color = "#0284c7";
    } else {
      badge.innerText = `Cat: ${targetName.substring(0, 10)}${targetName.length > 10 ? ".." : ""}`;
      badge.style.background = "#fef08a"; badge.style.color = "#854d0e";
    }

    const cWidth = panel.clientWidth, cHeight = panel.clientHeight;
    const margin = { top: 5, right: 10, bottom: 20, left: 30 };
    const innerW = cWidth - margin.left - margin.right, innerH = cHeight - margin.top - margin.bottom;

    const cSvg = d3.select("#mini-delta-chart").append("svg").attr("width", cWidth).attr("height", cHeight);
    const gChart = cSvg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    deltaChartXScale = d3.scaleLinear().domain([0, Math.max(1, evoTotalCommits - 1)]).range([0, innerW]);

    const maxVal = d3.max(deltaData, d => Math.max(d.added, d.deleted)) || 1;
    const yDeltaScale = d3.scaleLinear().domain([-maxVal, maxVal]).range([innerH, 0]);

    gChart.append("line").attr("x1", 0).attr("x2", innerW).attr("y1", yDeltaScale(0)).attr("y2", yDeltaScale(0))
      .attr("stroke", "#94a3b8").attr("stroke-width", 1.5).attr("stroke-dasharray", "2,2");

    gChart.append("g").attr("transform", `translate(0,${innerH})`)
      .call(d3.axisBottom(deltaChartXScale).ticks(5).tickFormat(d => `C${d + 1}`)).selectAll("text").style("fill", "#64748b");
    gChart.append("g").call(d3.axisLeft(yDeltaScale).ticks(5)).selectAll("text").style("fill", "#64748b");
    gChart.selectAll(".domain, .tick line").style("stroke", "#cbd5e1");

    const barWidth = Math.min(10, Math.max(2, (innerW / evoTotalCommits) * 0.7));

    gChart.selectAll(".bar-add").data(deltaData).enter().append("rect").attr("class", "bar-add")
      .attr("x", d => deltaChartXScale(d.idx) - (barWidth / 2))
      .attr("y", d => yDeltaScale(d.added))
      .attr("width", barWidth)
      .attr("height", d => yDeltaScale(0) - yDeltaScale(d.added))
      .attr("fill", "#10b981").attr("rx", 1);

    gChart.selectAll(".bar-del").data(deltaData).enter().append("rect").attr("class", "bar-del")
      .attr("x", d => deltaChartXScale(d.idx) - (barWidth / 2))
      .attr("y", d => yDeltaScale(0))
      .attr("width", barWidth)
      .attr("height", d => yDeltaScale(-d.deleted) - yDeltaScale(0))
      .attr("fill", "#ef4444").attr("rx", 1);

    deltaPlayheadLine = gChart.append("line").attr("y1", 0).attr("y2", innerH)
      .attr("stroke", "#3b82f6").attr("stroke-width", 1.5).attr("stroke-dasharray", "4,2").attr("x1", 0).attr("x2", 0);
  }

  function updateChartLegend(index, targetName) {
    const commitInfo = evoCommitsData[index];
    if (!commitInfo) return;

    let added = 0, deleted = 0;
    if (targetName === "global") {
      added = commitInfo.stats.delta.global.added;
      deleted = commitInfo.stats.delta.global.deleted;
    } else {
      const deltaStats = (commitInfo.stats.delta.by_category && commitInfo.stats.delta.by_category[targetName]) || { added: 0, deleted: 0 };
      added = deltaStats.added;
      deleted = deltaStats.deleted;
    }

    document.getElementById("leg-added").innerHTML = `Added: <strong>${added}</strong>`;
    document.getElementById("leg-deleted").innerHTML = `Deleted: <strong>${deleted}</strong>`;
  }

  /* FOCUS / FILTER LOGIC */
  function applyFocus(tree, focus) {
    if (!focus) return tree;
    const filtered = Object.assign({}, tree, { children: [] });
    if (focus.type === "category") {
      const cat = (tree.children || []).find(c => c.name === focus.name);
      if (cat) filtered.children = [cat];
    } else if (focus.type === "label") {
      const cat = (tree.children || []).find(c => c.name === focus.catName);
      if (cat) {
        const lbl = (cat.children || []).find(l => l.name === focus.labelName);
        if (lbl) filtered.children = [Object.assign({}, cat, { children: [lbl] })];
      }
    }
    return filtered;
  }

  window.clearEvoFocus = function () {
    evoActiveFocus = null;
    document.getElementById("focus-indicator").style.display = "none";
    updateGraph(parseInt(evoSlider.value));
  };

  function showDetails(nodeData) {
    const panel = document.getElementById("details-panel");
    const content = document.getElementById("details-content");
    let html = `<strong>Type: ${nodeData.group.toUpperCase()}</strong><br>`;
    if (nodeData.diff_status === "deleted") {
      html += `<div style="background:#fef2f2;border:1px solid #fca5a5;color:#ef4444;padding:8px;border-radius:6px;margin:10px 0;font-size:0.85rem;">Ghost Node: deleted here.</div>`;
    }
    if (nodeData.details) html += `<div style="margin-top:10px;">${nodeData.details}</div>`;
    if (nodeData.raw_text) {
      html += `<hr style="border:0;border-top:1px solid #e2e8f0;margin:15px 0;">
        <strong>Raw Content:</strong><pre style="white-space:pre-wrap;font-family:monospace;font-size:0.85rem;background:#f8fafc;padding:10px;border-radius:6px;border:1px solid #e2e8f0;">${nodeData.raw_text}</pre>`;
    }
    content.innerHTML = html;
    panel.style.display = "block";
  }

  function autoFitGraph(nodes) {
    if (!document.getElementById("evo-auto-fit").checked || nodes.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.forEach(n => {
      if (n.x < minX) minX = n.x; if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y; if (n.y + (n.data.width || 200) > maxY) maxY = n.y + (n.data.width || 200);
    });
    const treeH = maxX - minX, treeW = maxY - minY;
    const availableW = width - 80, availableH = height - 220;
    const scale = Math.min(availableW / (treeW || 1), availableH / (treeH || 1), 1.1);
    const tx = width / 2 - (minY + treeW / 2) * scale;
    const ty = 40 + (availableH / 2) - (minX + treeH / 2) * scale;
    evoSvg.transition().duration(800).call(evoZoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }

  /* UPDATE GRAPH */
  function updateGraph(index) {
    const commitInfo = evoCommitsData[index];
    document.getElementById("evo-commit-sha").innerText = commitInfo.commit.substring(0, 8);
    document.getElementById("evo-current-step").innerText = `Commit ${index + 1} of ${evoTotalCommits}`;

    let expectedChartTarget = "global";
    if (evoActiveFocus) {
      if (evoActiveFocus.type === "category") expectedChartTarget = evoActiveFocus.name;
      if (evoActiveFocus.type === "label") expectedChartTarget = evoActiveFocus.catName;
    }

    if (deltaChartTarget !== expectedChartTarget) {
      renderDeltaChart(expectedChartTarget);
    }
    if (deltaPlayheadLine && deltaChartXScale) {
      deltaPlayheadLine.transition().duration(300).attr("x1", deltaChartXScale(index)).attr("x2", deltaChartXScale(index));
    }

    updateChartLegend(index, expectedChartTarget);

    const rawData = commitInfo.tree;
    const rootData = applyFocus(rawData, evoActiveFocus);
    const root = d3.hierarchy(rootData);

    root.each(d => { if (evoCollapsedNodes.has(d.data.id) && d.children) { d._children = d.children; d.children = null; } });
    root.sort((a, b) => a.data.name.localeCompare(b.data.name));
    treeLayout(root);

    const nodes = root.descendants(), links = root.links();
    const numRules = nodes.filter(n => n.data.group === "rule").length;
    const numDeleted = nodes.filter(n => n.data.diff_status === "deleted").length;
    document.getElementById("evo-header-stats").innerHTML = `
      <span style="background:#e2e8f0;padding:2px 8px;border-radius:4px;font-weight:600;">Visible Nodes: ${nodes.length - 1}</span>
      <span style="background:#e2e8f0;padding:2px 8px;border-radius:4px;font-weight:600;">Visible Rules: ${numRules}</span>
      ${numDeleted > 0 ? `<span style="background:#fecaca;color:#991b1b;padding:2px 8px;border-radius:4px;font-weight:600;">Ghosts: ${numDeleted}</span>` : ""}
    `;

    autoFitGraph(nodes);

    const link = evoG.select(".links").selectAll("path.link").data(links, d => d.target.data.id);
    const linkEnter = link.enter().append("path").attr("class", "link")
      .attr("d", d => d3.linkHorizontal().x(d => d.y).y(d => d.x)({ source: d.source, target: d.source })).style("opacity", 0);
    link.merge(linkEnter).transition().duration(800)
      .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x))
      .style("opacity", d => d.target.data.diff_status === "deleted" ? 0.4 : 1)
      .attr("stroke", d => d.target.data.diff_status === "deleted" ? "#ef4444" : "#cbd5e1")
      .style("stroke-dasharray", d => d.target.data.diff_status === "deleted" ? "5,5" : "none");
    link.exit().transition().duration(500).style("opacity", 0).remove();

    const node = evoG.select(".nodes").selectAll("g.node").data(nodes, d => d.data.id);
    const nodeEnter = node.enter().append("g").attr("class", "node")
      .attr("transform", d => `translate(${d.parent ? d.parent.y : d.y},${d.parent ? d.parent.x : d.x})`)
      .style("opacity", 0);

    nodeEnter.filter(d => d.data.group !== "root").append("rect").attr("class", "main-rect")
      .attr("rx", 6).attr("ry", 6)
      .attr("fill", d => d.data.color).attr("stroke", "#0f172a");

    nodeEnter.filter(d => d.data.group === "root").append("image")
      .attr("href", "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23334155' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/></svg>")
      .attr("width", 32).attr("height", 32).attr("x", -16).attr("y", -16);

    nodeEnter.append("rect").attr("class", "text-bg").attr("fill", "rgba(255,255,255,0.75)").attr("rx", 3);
    nodeEnter.append("text").attr("class", "node-label")
      .attr("dy", d => d.data.group === "root" ? "28px" : "0.31em")
      .attr("x", d => d.data.group === "root" ? 0 : 12)
      .attr("text-anchor", d => d.data.group === "root" ? "middle" : "start")
      .style("fill", "#0f172a").style("font-weight", "500");

    const nodeUpdate = nodeEnter.merge(node);
    nodeUpdate.attr("class", d => {
      let cls = "node";
      if (d.data.diff_status === "added" && index > 0) cls += " node-added";
      if (d.data.diff_status === "deleted") cls += " node-deleted";
      if (d.data.id === evoSelectedNodeId) cls += " node-selected";
      return cls;
    });

    nodeUpdate.on("click", (event, d) => {
      event.stopPropagation();
      const mode = document.querySelector('input[name="evo-interaction-mode"]:checked').value;
      if (mode === "focus") {
        document.getElementById("details-panel").style.display = "none";
        if (d.data.group === "root") { window.clearEvoFocus(); }
        else if (d.data.group === "category" || d.data.group === "label") {
          evoActiveFocus = d.data.group === "category"
            ? { type: "category", name: d.data.name }
            : { type: "label", catName: d.parent.data.name, labelName: d.data.name };
          const ind = document.getElementById("focus-indicator");
          ind.style.display = "flex";
          document.getElementById("focus-name").innerText = d.data.name;
          updateGraph(parseInt(evoSlider.value));
        }
      } else {
        showDetails(d.data);
        if (d.data.group !== "root" && d.data.group !== "rule") {
          evoCollapsedNodes.has(d.data.id) ? evoCollapsedNodes.delete(d.data.id) : evoCollapsedNodes.add(d.data.id);
          updateGraph(parseInt(evoSlider.value));
        }
      }
      if (d.data.group === "rule" && d.data.raw_text) {
        evoSelectedNodeId = d.data.id;
        console.log("[AgentLens] evo highlightRule: text length =", d.data.raw_text.length);
        if (typeof vscode !== "undefined") vscode.postMessage({ command: "highlightRule", text: d.data.raw_text });
      } else {
        evoSelectedNodeId = null;
        console.log("[AgentLens] evo clearHighlight");
        if (typeof vscode !== "undefined") vscode.postMessage({ command: "clearHighlight" });
      }
    });

    nodeUpdate.select(".main-rect")
      .attr("width", d => d.data.width || 150)
      .attr("height", d => d.data.height || 36)
      .attr("y", d => -(d.data.height || 36) / 2)
      .attr("stroke-dasharray", d => d._children ? "4,4" : (d.data.diff_status === "deleted" ? "4,4" : "none"))
      .attr("stroke-width", d => d._children ? 3 : (d.data.border_width || 2));

    nodeUpdate.select(".node-label").each(function (d) {
      let textStr = d.data.name;
      if (d.data.group === "rule") {
        const maxW = (d.data.width || 150) - 24;
        this.textContent = textStr;
        if (this.getComputedTextLength() > maxW && textStr.length > 3) {
          let idx = textStr.length;
          while (this.getComputedTextLength() > maxW && idx > 0) { idx--; this.textContent = textStr.slice(0, idx) + "..."; }
        }
      } else this.textContent = textStr;
    });

    nodeUpdate.each(function (d) {
      const tNode = d3.select(this).select(".node-label").node();
      if (tNode && tNode.getBBox && d.data.group !== "root") {
        const bbox = tNode.getBBox();
        d3.select(this).select(".text-bg").attr("x", bbox.x - 4).attr("y", bbox.y - 2).attr("width", bbox.width + 8).attr("height", bbox.height + 4);
      }
    });

    nodeUpdate.each(function (d) {
      const el = d3.select(this);
      el.selectAll(".metric-badges-container").remove();
      if (!d.data.metrics || d.data.group === "root") return;

      let badges = [];
      if (d.data.group === "category") {
        badges = [
          { label: "LBL", val: d.data.metrics.lbls, bg: "#dbeafe", color: "#1e40af", border: "#bfdbfe" },
          { label: "RUL", val: d.data.metrics.rls, bg: "#d1fae5", color: "#065f46", border: "#a7f3d0" },
          { label: "COD", val: d.data.metrics.code, bg: "#f3e8ff", color: "#6b21a8", border: "#e9d5ff" }
        ];
      } else if (d.data.group === "label") {
        badges = [
          { label: "RUL", val: d.data.metrics.rls, bg: "#d1fae5", color: "#065f46", border: "#a7f3d0" },
          { label: "FRE", val: d.data.metrics.fre, bg: "#ffedd5", color: "#9a3412", border: "#fed7aa" },
          { label: "COD", val: d.data.metrics.code, bg: "#f3e8ff", color: "#6b21a8", border: "#e9d5ff" }
        ];
      } else if (d.data.group === "rule") {
        badges = [
          { label: "LEN", val: d.data.metrics.len, bg: "#f1f5f9", color: "#475569", border: "#cbd5e1" },
          { label: "SYM", val: d.data.metrics.sym, bg: "#fef2f2", color: "#991b1b", border: "#fecaca" }
        ];
      }

      const isGhost = (d.data.diff_status === "deleted");
      const rectHeight = d.data.height || 36;
      const badgeGroup = el.append("g").attr("class", "metric-badges-container").attr("transform", `translate(0,${-(rectHeight / 2) - 8})`);
      let currentX = 0;
      badges.forEach(b => {
        const bg = badgeGroup.append("g").attr("transform", `translate(${currentX},0)`);
        const t = bg.append("text").attr("font-size", "8px").attr("font-weight", "700").attr("font-family", "system-ui, sans-serif").attr("fill", isGhost ? "#94a3b8" : b.color).text(`${b.label}: ${b.val}`);
        const w = t.node().getComputedTextLength() + 8;
        bg.insert("rect", "text").attr("width", w).attr("height", 14).attr("y", -10).attr("rx", 3).attr("fill", isGhost ? "#f8fafc" : b.bg).attr("stroke", isGhost ? "#e2e8f0" : b.border).attr("stroke-width", 1);
        t.attr("x", 4); currentX += w + 4;
      });
    });

    nodeUpdate.transition().duration(800).attr("transform", d => `translate(${d.y},${d.x})`).style("opacity", 1);
    node.exit().transition().duration(500).attr("transform", d => `translate(${d.parent ? d.parent.y : d.y - 20},${d.parent ? d.parent.x : d.x})`).style("opacity", 0).remove();
  }

  /* PLAYBACK */
  let playInterval, isPlaying = false;
  function togglePlay() {
    isPlaying = !isPlaying;
    if (isPlaying) {
      if (parseInt(evoSlider.value) >= evoTotalCommits - 1) evoSlider.value = 0;
      document.getElementById("evo-play-btn").innerHTML =
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';
      updateGraph(parseInt(evoSlider.value));
      playInterval = setInterval(() => {
        let val = parseInt(evoSlider.value);
        if (val >= evoTotalCommits - 1) { togglePlay(); return; }
        evoSlider.value = val + 1; updateGraph(val + 1);
      }, 1800);
    } else {
      document.getElementById("evo-play-btn").innerHTML =
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
      clearInterval(playInterval);
    }
  }

  document.getElementById("evo-play-btn").addEventListener("click", togglePlay);
  evoSlider.addEventListener("input", (e) => { if (isPlaying) togglePlay(); updateGraph(parseInt(e.target.value)); });
  window.addEventListener("resize", () => {
    evoSvg.attr("width", container.clientWidth).attr("height", container.clientHeight);
    if (evoTotalCommits > 0) updateGraph(parseInt(evoSlider.value));
  });

  renderDeltaChart("global");
  updateGraph(0);
}
