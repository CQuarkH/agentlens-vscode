let staticSvg = null;
let staticG = null;
let staticZoom = null;
let staticRoot = null;
let selectedNodeId = null;

function renderStaticTree(treeData) {
  const container = document.getElementById("static-graph-container");
  container.innerHTML = "";

  const legendPanel = document.createElement("div");
  legendPanel.className = "legend-panel";
  legendPanel.style.cssText = "position:absolute;top:10px;left:16px;background:rgba(255,255,255,0.95);border:1px solid #e2e8f0;border-radius:12px;padding:10px 14px;box-shadow:0 4px 15px rgba(0,0,0,0.05);z-index:100;font-size:11px;color:#475569;transition:all 0.2s ease;";
  legendPanel.innerHTML = `
    <div class="legend-header" style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;" onclick="toggleStaticLegend(this.parentElement, this)">
      <h4 style="margin:0;font-size:11px;color:#0f172a;text-transform:uppercase;display:flex;align-items:center;gap:6px;">
        <span style="font-size:0.7rem;color:#94a3b8;" class="toggle-icon">&#9660;</span>
        Metrics
      </h4>
    </div>
    <div class="legend-body" style="padding-top:8px;">
      <div style="display:grid;grid-template-columns:auto auto;gap:4px 14px;">
        <div><span class="legend-badge lb-lbl">LBL</span> Labels</div>
        <div><span class="legend-badge lb-rul">RUL</span> Rules</div>
        <div><span class="legend-badge lb-cod">COD</span> Code Ratio</div>
        <div><span class="legend-badge lb-fre">FRE</span> Readability</div>
        <div><span class="legend-badge lb-len">LEN</span> Length</div>
        <div><span class="legend-badge lb-sym">SYM</span> Symbols</div>
      </div>
    </div>
  `;
  container.appendChild(legendPanel);

  function toggleStaticLegend(panel, headerEl) {
    const body = panel.querySelector(".legend-body");
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

  const width = container.clientWidth;
  const height = container.clientHeight;

  staticSvg = d3.select("#static-graph-container")
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  staticG = staticSvg.append("g");

  staticZoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on("zoom", (event) => {
      staticG.attr("transform", event.transform);
    });

  staticSvg.call(staticZoom);
  staticSvg.on("click", () => {
    selectedNodeId = null;
    if (typeof vscode !== "undefined") vscode.postMessage({ command: "clearHighlight" });
  });

  let root = d3.hierarchy(treeData);
  let i = 0;

  root.descendants().forEach(d => {
    if (d.depth >= 1) {
      d._children = d.children;
      d.children = null;
    }
  });

  const dx = 1;
  const dy = 320;
  const treeLayout = d3.tree()
    .nodeSize([dx, dy])
    .separation((a, b) => {
      const hA = a.data.height || 40;
      const hB = b.data.height || 40;
      return (hA + hB) / 2 + 30;
    });

  staticG.append("g").attr("class", "links");
  staticG.append("g").attr("class", "nodes");
  staticG.attr("transform", `translate(${dy / 2},${height / 2})`);

  function staticUpdate(source) {
    treeLayout(root);

    const nodes = root.descendants();
    const links = root.links();

    const link = staticG.select(".links").selectAll("path.link")
      .data(links, d => d.target.id || (d.target.id = ++i));

    const linkEnter = link.enter().append("path")
      .attr("class", "link")
      .attr("d", d => {
        const o = { x: source.x0 || source.x, y: source.y0 || source.y };
        return d3.linkHorizontal().x(d => d.y).y(d => d.x)({ source: o, target: o });
      });

    link.merge(linkEnter).transition().duration(400)
      .attr("d", d3.linkHorizontal().x(d => d.y).y(d => d.x));

    link.exit().transition().duration(400)
      .attr("d", d => {
        const o = { x: source.x, y: source.y };
        return d3.linkHorizontal().x(d => d.y).y(d => d.x)({ source: o, target: o });
      }).remove();

    const node = staticG.select(".nodes").selectAll("g.node")
      .data(nodes, d => d.id || (d.id = ++i));

    const nodeEnter = node.enter().append("g")
      .attr("class", "node")
      .attr("transform", d => `translate(${source.y0 || source.y},${source.x0 || source.x})`)
      .on("click", (event, d) => {
        showStaticDetails(d.data, event.currentTarget);

        if (d.children) {
          d._children = d.children;
          d.children = null;
        } else if (d._children) {
          d.children = d._children;
          d._children = null;
        }

        if (d.data.group === "rule" && d.data.raw_text) {
          selectedNodeId = d.id;
          console.log("[AgentLens] highlightRule: text length =", d.data.raw_text.length);
          if (typeof vscode !== "undefined") vscode.postMessage({ command: "highlightRule", text: d.data.raw_text });
        } else {
          selectedNodeId = null;
          console.log("[AgentLens] clearHighlight");
          if (typeof vscode !== "undefined") vscode.postMessage({ command: "clearHighlight" });
        }
        staticUpdate(d);
      });

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
      .attr("width", 32).attr("height", 32).attr("x", -16).attr("y", -16);

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

    nodeUpdate.select(".node-label").each(function (d) {
      if (d.data.group === "rule") {
        const padding = 24;
        const maxWidth = (d.data.width || 120) - padding;
        let textStr = d.data.name;
        this.textContent = textStr;

        if (this.getComputedTextLength() > maxWidth && textStr.length > 3) {
          let i = textStr.length;
          while (this.getComputedTextLength() > maxWidth && i > 0) {
            i--;
            this.textContent = textStr.slice(0, i) + "...";
          }
        }
      }
    });

    nodeUpdate.each(function (d) {
      const textNode = d3.select(this).select(".node-label").node();
      if (textNode && textNode.getBBox) {
        const bbox = textNode.getBBox();
        if (d.data.group === "category" || d.data.group === "label" || d.data.group === "rule") {
          d3.select(this).select(".text-bg")
            .attr("x", bbox.x - 4)
            .attr("y", bbox.y - 2)
            .attr("width", bbox.width + 8)
            .attr("height", bbox.height + 4);
        } else {
          d3.select(this).select(".text-bg")
            .attr("width", 0).attr("height", 0);
        }
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

      const rectHeight = d.data.height || 36;
      const badgeGroup = el.append("g").attr("class", "metric-badges-container").attr("transform", `translate(0,${-(rectHeight / 2) - 8})`);
      let currentX = 0;
      badges.forEach(b => {
        const bg = badgeGroup.append("g").attr("transform", `translate(${currentX},0)`);
        const t = bg.append("text").attr("font-size", "8px").attr("font-weight", "700").attr("font-family", "system-ui, sans-serif").attr("fill", b.color).text(`${b.label}: ${b.val}`);
        const w = t.node().getComputedTextLength() + 8;
        bg.insert("rect", "text").attr("width", w).attr("height", 14).attr("y", -10).attr("rx", 3).attr("fill", b.bg).attr("stroke", b.border).attr("stroke-width", 1);
        t.attr("x", 4); currentX += w + 4;
      });
    });

    nodeUpdate.attr("class", d => {
      let cls = "node";
      if (d.id === selectedNodeId) cls += " node-selected";
      return cls;
    });

    nodeUpdate.transition().duration(400)
      .attr("transform", d => `translate(${d.y},${d.x})`);

    nodeUpdate.select("rect").transition().duration(400)
      .attr("stroke", "#0f172a");

    node.exit().transition().duration(400)
      .attr("transform", d => `translate(${source.y},${source.x})`)
      .style("opacity", 0)
      .remove();

    nodes.forEach(d => {
      d.x0 = d.x;
      d.y0 = d.y;
    });
  }

  root.x0 = height / 2;
  root.y0 = 0;
  staticUpdate(root);

  window.addEventListener("resize", () => {
    const newWidth = container.clientWidth;
    const newHeight = container.clientHeight;
    staticSvg.attr("width", newWidth).attr("height", newHeight);
  });
}

function showStaticDetails(nodeData) {
  const panel = document.getElementById("details-panel");
  const content = document.getElementById("details-content");
  let html = `<strong>${nodeData.group.toUpperCase()}</strong><br>`;
  html += nodeData.details || "No details available.";
  content.innerHTML = html;
  panel.style.display = "block";
}
