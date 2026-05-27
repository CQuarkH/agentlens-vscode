import * as vscode from "vscode";
import { BackendManager } from "./backendManager";
import { ASTWebview } from "./webview";

let backend: BackendManager;

export function activate(context: vscode.ExtensionContext): void {
  console.log("[AgentLens] Activating extension...");

  backend = new BackendManager();

  const disposable = vscode.commands.registerCommand("agentlens.showAST", async () => {
    if (!backend.isReady) {
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Starting AgentLens backend...",
          cancellable: false,
        },
        async () => {
          await backend.start();
        }
      );
    }

    const webview = new ASTWebview(backend);
    await webview.show();
  });

  context.subscriptions.push(disposable);

  context.subscriptions.push({
    dispose: () => {
      backend?.stop();
    },
  });
}

export function deactivate(): void {
  console.log("[AgentLens] Deactivating extension...");
  backend?.stop();
}
