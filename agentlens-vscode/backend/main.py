import json
import subprocess
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("agentlens-backend")

from cache_manager import (
    get_cached_tree, save_cached_tree,
    get_cached_evolution_tree, save_cached_evolution_tree,
    get_file_history, save_file_history
)
from ast_service import build_tree_data, parse_commit_tree, extract_timeline_data
from llm_service import extract_ast_with_llm, migrate_ast_schema


class TreeRequest(BaseModel):
    file_path: str
    repo: str
    commit: str | None = None


class EvolutionRequest(BaseModel):
    file_path: str
    repo: str


class GenerateRequest(BaseModel):
    file_path: str
    repo: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AgentLens backend started")
    yield
    logger.info("AgentLens backend stopped")


app = FastAPI(title="AgentLens Backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/tree")
async def get_tree(req: TreeRequest):
    logger.info(f"[/api/tree] repo={req.repo!r} file_path={req.file_path!r}")
    cached = get_cached_tree(req.repo, req.file_path)
    if cached:
        try:
            from domain_models import AgentASTDocument
            doc = AgentASTDocument.model_validate(cached)
            tree_data = build_tree_data(doc)
            return {"status": "cached", "data": tree_data}
        except Exception as e:
            logger.warning(f"Tree validation failed, returning raw data: {e}")
            return {"status": "cached", "data": cached}
    raise HTTPException(status_code=404, detail={
        "status": "not_found",
        "message": "AST not in cache. Use /api/generate to create it."
    })


@app.post("/api/evolution")
async def get_evolution(req: EvolutionRequest):
    file_path_obj = Path(req.file_path)

    file_history = get_file_history(req.repo)
    if not file_history:
        file_history = _fetch_git_history(file_path_obj)
        if not file_history:
            raise HTTPException(status_code=404, detail={
                "status": "error",
                "message": "No git history found for this file."
            })
        save_file_history(req.repo, file_history)

    missing_commits = []
    entries_with_dates = []
    for entry in file_history:
        sha = entry.get("sha") if isinstance(entry, dict) else entry
        date = entry.get("date", "") if isinstance(entry, dict) else ""
        raw = get_cached_evolution_tree(req.repo, sha)
        if raw:
            tree = parse_commit_tree(raw, sha, req.repo)
            if tree:
                entries_with_dates.append({"commit": sha, "date": date, "tree": tree})
            else:
                missing_commits.append(sha)
        else:
            missing_commits.append(sha)

    entries_with_dates.sort(key=lambda e: e["date"])
    cached_trees = [{"commit": e["commit"], "tree": e["tree"]} for e in entries_with_dates]

    if missing_commits:
        return {
            "status": "incomplete",
            "message": f"Missing ASTs for {len(missing_commits)} commits. Generate them first.",
            "missing_commits": missing_commits,
            "cached_count": len(cached_trees)
        }

    timeline = extract_timeline_data(cached_trees)
    return {"status": "complete", "data": timeline}


@app.post("/api/generate")
async def generate_ast(req: GenerateRequest):
    file_path = Path(req.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

    repo = req.repo or file_path.resolve().parent.name

    logger.info(f"Generating AST for {req.file_path} in repo {repo}")

    raw_json = extract_ast_with_llm(req.file_path)
    if not raw_json:
        raise HTTPException(status_code=500, detail="LLM extraction failed.")

    migrated = migrate_ast_schema(raw_json)

    save_cached_tree(repo, req.file_path, migrated)
    logger.info(f"AST generated and cached for {req.file_path}")

    try:
        from domain_models import AgentASTDocument
        doc = AgentASTDocument.model_validate(migrated)
        tree_data = build_tree_data(doc)
        return {"status": "generated", "data": tree_data}
    except Exception as e:
        logger.warning(f"Tree building failed after generation: {e}")
        return {"status": "generated", "data": migrated}


def _fetch_git_history(file_path: Path) -> list | None:
    try:
        repo_dir = _find_git_root(file_path)
        if not repo_dir:
            return None

        rel_path = file_path.resolve().relative_to(repo_dir)

        result = subprocess.run(
            ["git", "log", "--reverse", "--format=%H", "--", str(rel_path)],
            capture_output=True, text=True, cwd=repo_dir, timeout=30
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        shas = [sha.strip() for sha in result.stdout.strip().split("\n") if sha.strip()]

        import re
        commits_with_info = []
        for sha in shas:
            show_result = subprocess.run(
                ["git", "show", "--format=%ci|%s", "-s", sha],
                capture_output=True, text=True, cwd=repo_dir, timeout=30
            )
            parts = show_result.stdout.strip().split("|", 1)
            date = parts[0] if len(parts) > 0 else ""
            message = parts[1] if len(parts) > 1 else ""
            commits_with_info.append({
                "sha": sha,
                "date": date,
                "message": message.split("\n")[0]
            })

        return commits_with_info

    except Exception as e:
        logger.error(f"Git history fetch failed: {e}")
        return None


def _find_git_root(file_path: Path) -> Path | None:
    current = file_path.resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("AGENTLENS_PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
