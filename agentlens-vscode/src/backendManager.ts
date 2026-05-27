import * as vscode from "vscode";
import { ChildProcess, spawn } from "child_process";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

export class BackendManager {
  private process: ChildProcess | null = null;
  private port: number;
  private pythonPath: string;
  private ready: boolean = false;
  private pidFilePath: string;

  constructor() {
    const config = vscode.workspace.getConfiguration("agentlens");
    this.port = config.get<number>("backendPort", 8765);
    this.pythonPath = config.get<string>("pythonPath", "python3");
    this.pidFilePath = path.join(os.homedir(), ".agentlens", "backend.pid");
  }

  get isReady(): boolean {
    return this.ready;
  }

  get currentPort(): number {
    return this.port;
  }

  async start(): Promise<void> {
    this.killExistingProcess();

    const backendDir = this.getBackendDir();
    if (!backendDir) {
      vscode.window.showErrorMessage(
        "AgentLens: Could not find backend directory. Make sure the extension is properly installed."
      );
      return;
    }

    const mainPy = path.join(backendDir, "main.py");
    const projectRoot = this.getProjectRoot();

    const env: Record<string, string> = {
      ...process.env as Record<string, string>,
      AGENTLENS_PORT: String(this.port),
    };
    if (projectRoot) {
      env.PYTHONPATH = projectRoot;
    }
    const cacheRoot = vscode.workspace.getConfiguration("agentlens").get<string>("cacheRoot", "");
    if (cacheRoot) {
      env.AGENTLENS_CACHE_ROOT = cacheRoot;
    }

    this.process = spawn(this.pythonPath, [mainPy], {
      cwd: backendDir,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    });

    if (this.process.pid) {
      this.savePid(this.process.pid);
    }

    this.process.stdout?.on("data", (data: Buffer) => {
      console.log(`[AgentLens Backend] ${data.toString().trim()}`);
    });

    this.process.stderr?.on("data", (data: Buffer) => {
      console.error(`[AgentLens Backend] ${data.toString().trim()}`);
    });

    this.process.on("error", (err: Error) => {
      console.error("[AgentLens Backend] Failed to start:", err.message);
      vscode.window.showErrorMessage(
        `AgentLens: Failed to start backend. ${err.message}`
      );
      this.ready = false;
    });

    this.process.on("exit", (code: number | null) => {
      console.log(`[AgentLens Backend] Exited with code ${code}`);
      this.ready = false;
      this.process = null;
      this.removePid();
    });

    await this.waitForReady();
  }

  async stop(): Promise<void> {
    if (this.process) {
      this.process.kill("SIGTERM");
      this.process = null;
      this.ready = false;
    }
    this.removePid();
  }

  async restart(): Promise<void> {
    await this.stop();
    await this.start();
  }

  private killExistingProcess(): void {
    try {
      if (fs.existsSync(this.pidFilePath)) {
        const oldPid = parseInt(fs.readFileSync(this.pidFilePath, "utf-8").trim(), 10);
        if (oldPid > 0) {
          try {
            process.kill(oldPid, 0);
            process.kill(oldPid, "SIGTERM");
            console.log(`[AgentLens Backend] Killed old process ${oldPid}`);
          } catch {
            // Process already dead
          }
        }
        fs.unlinkSync(this.pidFilePath);
      }
    } catch {
      // Ignore errors reading PID file
    }
  }

  private savePid(pid: number): void {
    try {
      const dir = path.dirname(this.pidFilePath);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(this.pidFilePath, String(pid), "utf-8");
    } catch (e) {
      console.error("[AgentLens Backend] Failed to save PID file:", e);
    }
  }

  private removePid(): void {
    try {
      if (fs.existsSync(this.pidFilePath)) {
        fs.unlinkSync(this.pidFilePath);
      }
    } catch {
      // Ignore
    }
  }

  private async waitForReady(timeoutMs: number = 15000): Promise<void> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        const response = await fetch(`http://127.0.0.1:${this.port}/health`);
        if (response.ok) {
          this.ready = true;
          console.log(`[AgentLens Backend] Ready on port ${this.port}`);
          return;
        }
      } catch {
        // Backend not ready yet
      }
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    vscode.window.showErrorMessage(
      "AgentLens: Backend did not start in time. Check that Python dependencies are installed."
    );
  }
  private getBackendDir(): string | null {
    const possibleDirs = [
      path.join(__dirname, "..", "..", "backend"),
      path.join(__dirname, "..", "backend"),
      path.join(vscode.workspace.rootPath || "", "agentlens-vscode", "backend"),
    ];
    for (const dir of possibleDirs) {
      if (fs.existsSync(path.join(dir, "main.py"))) {
        return dir;
      }
    }
    return null;
  }

  private getProjectRoot(): string | null {
    const config = vscode.workspace.getConfiguration("agentlens");
    const configured = config.get<string>("projectRoot", "");
    if (configured) {
      return configured;
    }
    if (vscode.workspace.rootPath) {
      return vscode.workspace.rootPath;
    }
    return null;
  }
}
