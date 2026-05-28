import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { BackendManager } from "./backendManager";
import { ApiClient } from "./apiClient";

export class ASTWebview {
  private panel: vscode.WebviewPanel | null = null;
  private backend: BackendManager;
  private api: ApiClient;
  private highlightDecoration: vscode.TextEditorDecorationType | null = null;

  constructor(backend: BackendManager) {
    this.backend = backend;
    this.api = new ApiClient(backend.currentPort);
  }

  async show(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage("AgentLens: Open a Markdown file first.");
      return;
    }

    const filePath = editor.document.uri.fsPath;
    if (!filePath.endsWith(".md")) {
      vscode.window.showWarningMessage("AgentLens: Please open a Markdown file (.md).");
      return;
    }

    const repoName = this.detectRepoName(filePath);

    if (!this.panel) {
      this.panel = vscode.window.createWebviewPanel(
        "agentlens",
        `AgentLens: ${path.basename(filePath)}`,
        vscode.ViewColumn.Beside,
        {
          enableScripts: true,
          retainContextWhenHidden: true,
          localResourceRoots: [
            vscode.Uri.file(path.join(__dirname, "..", "media")),
          ],
        }
      );

      this.panel.onDidDispose(() => {
        this.panel = null;
      });
    } else {
      this.panel.reveal(vscode.ViewColumn.Beside);
    }

    const htmlContent = this.getWebviewHtml(filePath, repoName);
    this.panel.webview.html = htmlContent;

    this.panel.webview.onDidReceiveMessage(async (message) => {
      switch (message.command) {
        case "loadTree":
          await this.handleLoadTree(filePath, repoName);
          break;
        case "loadEvolution":
          await this.handleLoadEvolution(filePath, repoName);
          break;
        case "generateAST":
          await this.handleGenerate(filePath, repoName);
          break;
        case "generateMissingEvolution":
          await this.handleGenerateMissingEvolution(filePath, repoName, message.missingCommits || []);
          break;
        case "highlightRule":
          console.log("[AgentLens] Received highlightRule, text length:", message.text?.length);
          this.highlightRuleInEditor(message.text);
          break;
        case "clearHighlight":
          console.log("[AgentLens] Received clearHighlight");
          this.clearHighlight();
          break;
      }
    });
  }

  private async handleLoadTree(filePath: string, repoName: string): Promise<void> {
    if (!this.backend.isReady) {
      this.postMessage({ command: "treeStatus", status: "error", message: "Backend not ready." });
      return;
    }

    const result = await this.api.getTree(filePath, repoName);
    if (result.status === "cached") {
      this.postMessage({ command: "treeReady", data: result.data });
    } else {
      this.postMessage({
        command: "treeStatus",
        status: "not_found",
        message: "AST not cached. Generate using LLM?",
      });
    }
  }

  private async handleLoadEvolution(filePath: string, repoName: string): Promise<void> {
    if (!this.backend.isReady) {
      this.postMessage({ command: "evolutionStatus", status: "error", message: "Backend not ready." });
      return;
    }

    const result = await this.api.getEvolution(filePath, repoName);
    if (result.status === "complete") {
      this.postMessage({ command: "evolutionReady", data: result.data });
    } else if (result.status === "incomplete") {
      this.postMessage({
        command: "evolutionStatus",
        status: "incomplete",
        message: `Missing ASTs for ${result.missing_commits?.length} commits. Generate them?`,
        missingCommits: result.missing_commits,
      });
    } else {
      this.postMessage({
        command: "evolutionStatus",
        status: "error",
        message: result.message || "Failed to load evolution data.",
      });
    }
  }

  private async handleGenerate(filePath: string, repoName: string): Promise<void> {
    const choice = await vscode.window.showInformationMessage(
      "The AST is not in cache. Do you want to generate it using the LLM API? (This will consume API credits)",
      "Yes",
      "Cancel"
    );

    if (choice !== "Yes") {
      this.postMessage({ command: "treeStatus", status: "cancelled" });
      return;
    }

    this.postMessage({ command: "treeStatus", status: "generating" });

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Generating AST via LLM...",
        cancellable: false,
      },
      async () => {
        const result = await this.api.generate(filePath, repoName);
        if (result.status === "generated") {
          this.postMessage({ command: "treeReady", data: result.data });
        } else {
          this.postMessage({
            command: "treeStatus",
            status: "error",
            message: result.message || "Generation failed.",
          });
          vscode.window.showErrorMessage(`AgentLens: AST generation failed. ${result.message || ""}`);
        }
      }
    );
  }

  private async handleGenerateMissingEvolution(
    filePath: string,
    repoName: string,
    missingCommits: string[]
  ): Promise<void> {
    const choice = await vscode.window.showInformationMessage(
      `AgentLens: ${missingCommits.length} commit ASTs are missing. Generate all using LLM? (This will consume API credits)`,
      "Yes",
      "Cancel"
    );

    if (choice !== "Yes") {
      return;
    }

    this.postMessage({ command: "evolutionStatus", status: "generating" });

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Generating ${missingCommits.length} commit ASTs...`,
        cancellable: false,
      },
      async () => {
        for (let i = 0; i < missingCommits.length; i++) {
          this.postMessage({
            command: "evolutionGenerationProgress",
            current: i + 1,
            total: missingCommits.length,
          });
          await this.api.generate(filePath, repoName, missingCommits[i]);
        }
        const result = await this.api.getEvolution(filePath, repoName);
        if (result.status === "complete") {
          this.postMessage({ command: "evolutionReady", data: result.data });
        } else {
          this.postMessage({
            command: "evolutionStatus",
            status: "error",
            message: "Some commits could not be generated.",
          });
        }
      }
    );
  }

  private highlightRuleInEditor(text: string): void {
    const editor = this.findMarkdownEditor();
    if (!editor) {
      console.log("[AgentLens] highlight: no markdown editor found");
      return;
    }

    this.clearHighlight();

    const doc = editor.document;
    const docText = doc.getText();
    console.log("[AgentLens] highlight: searching text length", text.length, "in doc length", docText.length);
    console.log("[AgentLens] highlight: first 100 chars:", JSON.stringify(text.substring(0, 100)));

    const firstExact = docText.indexOf(text);
    if (firstExact !== -1) {
      console.log("[AgentLens] highlight: EXACT match at index", firstExact);
      this.applyHighlight(doc, docText, text, firstExact, editor);
      return;
    }

    console.log("[AgentLens] highlight: exact NOT FOUND, trying line-match");
    const norm = (s: string) => s.replace(/\s+/g, " ").trim();
    const needleNorm = norm(text);
    for (let lineIdx = 0; lineIdx < doc.lineCount; lineIdx++) {
      const line = doc.lineAt(lineIdx);
      if (norm(line.text).includes(needleNorm) || needleNorm.includes(norm(line.text))) {
        console.log("[AgentLens] highlight: fuzzy line match at line", lineIdx);
        const range = line.range;
        this.applyHighlightRange(editor, range);
        editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
        return;
      }
    }

    console.log("[AgentLens] highlight: text NOT FOUND in document");
  }

  private findMarkdownEditor(): vscode.TextEditor | undefined {
    for (const e of vscode.window.visibleTextEditors) {
      if (e.document.fileName.endsWith(".md")) {
        return e;
      }
    }
    return vscode.window.activeTextEditor ?? undefined;
  }

  private applyHighlight(doc: vscode.TextDocument, docText: string, matchText: string, startIdx: number, editor: vscode.TextEditor): void {
    const ranges: vscode.Range[] = [];
    let searchFrom = startIdx;
    while (true) {
      const idx = docText.indexOf(matchText, searchFrom);
      if (idx === -1) break;
      ranges.push(new vscode.Range(doc.positionAt(idx), doc.positionAt(idx + matchText.length)));
      searchFrom = idx + matchText.length;
    }
    this.applyHighlightRange(editor, ...ranges);
    if (ranges.length > 0) {
      editor.revealRange(ranges[0], vscode.TextEditorRevealType.InCenter);
    }
  }

  private applyHighlightRange(editor: vscode.TextEditor, ...ranges: vscode.Range[]): void {
    if (!this.highlightDecoration) {
      this.highlightDecoration = vscode.window.createTextEditorDecorationType({
        backgroundColor: "rgba(255, 200, 0, 0.2)",
        border: "1px solid rgba(255, 200, 0, 0.5)",
        borderRadius: "3px",
        overviewRulerColor: "rgba(255, 200, 0, 0.6)",
        overviewRulerLane: vscode.OverviewRulerLane.Center,
      });
    }
    editor.setDecorations(this.highlightDecoration, ranges);
  }

  private clearHighlight(): void {
    const editor = vscode.window.activeTextEditor;
    if (editor && this.highlightDecoration) {
      editor.setDecorations(this.highlightDecoration, []);
    }
  }

  private postMessage(message: any): void {
    this.panel?.webview.postMessage(message);
  }

  private detectRepoName(filePath: string): string {
    return path.basename(filePath, ".md");
  }

  private getWebviewHtml(filePath: string, repoName: string): string {
    const mediaDir = vscode.Uri.file(path.join(__dirname, "..", "media"));
    const baseUri = this.panel!.webview.asWebviewUri(mediaDir);
    const fileName = path.basename(filePath);

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AgentLens: ${fileName}</title>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <link rel="stylesheet" href="${baseUri}/styles.css">
</head>
<body>
  <div class="header-bar">
    <h1 class="header-title">AgentLens: ${fileName}</h1>
    <span class="repo-badge">${repoName}</span>
  </div>

  <div class="tab-bar">
    <button class="tab-btn active" data-tab="static-tree">Static Tree</button>
    <button class="tab-btn" data-tab="evolution-timeline">Evolution Timeline</button>
  </div>

  <div class="tab-content active" id="tab-static-tree">
    <div id="static-view-controls">
      <button id="btn-load-tree" class="action-btn">Load Static Tree</button>
      <span id="static-status" class="status-msg"></span>
    </div>
    <div id="static-graph-container" class="graph-container">
      <p class="placeholder-text">Click "Load Static Tree" to view the AST hierarchy.</p>
    </div>
  </div>

  <div class="tab-content" id="tab-evolution-timeline">
    <div id="evolution-view-controls">
      <button id="btn-load-evolution" class="action-btn">Load Evolution Timeline</button>
      <span id="evolution-status" class="status-msg"></span>
    </div>
    <div id="evolution-graph-container" class="graph-container">
      <p class="placeholder-text">Click "Load Evolution Timeline" to view the diff history.</p>
    </div>
  </div>

  <div id="details-panel" style="display:none;">
    <span class="close-btn" onclick="this.parentElement.style.display='none'">&times;</span>
    <h3>Node Details</h3>
    <div id="details-content"></div>
  </div>

  <div id="loading-overlay" style="display:none;">
    <div class="spinner"></div>
    <p id="loading-text">Loading...</p>
  </div>

  <script src="${baseUri}/staticView.js"></script>
  <script src="${baseUri}/evolutionView.js"></script>
  <script>
    const vscode = acquireVsCodeApi();
    let currentTab = "static-tree";

    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        currentTab = btn.dataset.tab;
        document.getElementById("tab-" + currentTab).classList.add("active");
      });
    });

    document.getElementById("btn-load-tree").addEventListener("click", () => {
      vscode.postMessage({ command: "loadTree" });
    });

    document.getElementById("btn-load-evolution").addEventListener("click", () => {
      vscode.postMessage({ command: "loadEvolution" });
    });

    let pendingMissingCommits = null;

    window.addEventListener("message", (event) => {
      const msg = event.data;

      switch (msg.command) {
        case "treeReady":
          document.getElementById("static-status").textContent = "";
          hideLoading();
          renderStaticTree(msg.data);
          break;
        case "treeStatus":
          if (msg.status === "not_found") {
            document.getElementById("static-status").innerHTML =
              '<span class="warn">AST not cached. <a href="#" onclick="requestGenerate()">Generate via LLM</a></span>';
          } else if (msg.status === "generating") {
            showLoading("Generating AST via LLM...");
          } else if (msg.status === "cancelled") {
            document.getElementById("static-status").textContent = "Cancelled.";
          } else if (msg.status === "error") {
            document.getElementById("static-status").innerHTML =
              '<span class="error">' + msg.message + '</span>';
            hideLoading();
          }
          break;
        case "evolutionReady":
          document.getElementById("evolution-status").textContent = "";
          hideLoading();
          renderEvolution(msg.data);
          break;
        case "evolutionStatus":
          if (msg.status === "incomplete") {
            pendingMissingCommits = msg.missingCommits;
            document.getElementById("evolution-status").innerHTML =
              '<span class="warn">' + msg.message + ' <a href="#" onclick="requestGenerateEvolution()">Generate All</a></span>';
          } else if (msg.status === "generating") {
            showLoading("Generating evolution ASTs...");
          } else if (msg.status === "error") {
            document.getElementById("evolution-status").innerHTML =
              '<span class="error">' + msg.message + '</span>';
            hideLoading();
          }
          break;
        case "evolutionGenerationProgress":
          document.getElementById("loading-text").textContent =
            "Generating commit " + msg.current + " of " + msg.total + "...";
          break;
      }
    });

    function requestGenerate() {
      vscode.postMessage({ command: "generateAST" });
    }

    function requestGenerateEvolution() {
      vscode.postMessage({ command: "generateMissingEvolution", missingCommits: pendingMissingCommits });
    }

    function showLoading(text) {
      document.getElementById("loading-text").textContent = text;
      document.getElementById("loading-overlay").style.display = "flex";
    }

    function hideLoading() {
      document.getElementById("loading-overlay").style.display = "none";
    }
  </script>
</body>
</html>`;
  }
}
