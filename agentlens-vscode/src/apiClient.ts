export interface TreeResponse {
  status: "cached" | "not_found";
  data?: any;
  message?: string;
}

export interface EvolutionResponse {
  status: "complete" | "incomplete" | "error";
  data?: any;
  message?: string;
  missing_commits?: string[];
  cached_count?: number;
}

export interface GenerateResponse {
  status: "generated" | "error";
  data?: any;
  message?: string;
}

export class ApiClient {
  private baseUrl: string;

  constructor(port: number) {
    this.baseUrl = `http://127.0.0.1:${port}`;
  }

  async health(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/health`);
      return res.ok;
    } catch {
      return false;
    }
  }

  async getTree(filePath: string, repo: string, commit?: string): Promise<TreeResponse> {
    const res = await fetch(`${this.baseUrl}/api/tree`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, repo, commit }),
    });
    if (res.status === 404) {
      const detail = await res.json();
      return { status: "not_found", message: detail.detail?.message || "Not found" };
    }
    if (!res.ok) {
      return { status: "not_found", message: `HTTP ${res.status}` };
    }
    return await res.json();
  }

  async getEvolution(filePath: string, repo: string): Promise<EvolutionResponse> {
    const res = await fetch(`${this.baseUrl}/api/evolution`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, repo }),
    });
    if (!res.ok) {
      const detail = await res.json();
      return { status: "error", message: detail.detail?.message || `HTTP ${res.status}` };
    }
    return await res.json();
  }

  async generate(filePath: string, repo?: string): Promise<GenerateResponse> {
    const res = await fetch(`${this.baseUrl}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_path: filePath, repo }),
    });
    if (!res.ok) {
      return { status: "error", message: `HTTP ${res.status}` };
    }
    return await res.json();
  }
}
