import json
import os
import tempfile
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.request import Request, urlopen
from urllib.error import HTTPError

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
    commit: str | None = None


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

    repo = req.repo or file_path.resolve().parent.name
    logger.info(f"Generating AST for {req.file_path} in repo {repo}" + (f" at commit {req.commit}" if req.commit else ""))

    if req.commit:
        content = _read_file_at_commit(file_path, req.commit)
        if content is None:
            raise HTTPException(status_code=500, detail=f"Failed to read file at commit {req.commit}")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            raw_json = extract_ast_with_llm(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    else:
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
        raw_json = extract_ast_with_llm(str(file_path))

    if not raw_json:
        raise HTTPException(status_code=500, detail="LLM extraction failed.")

    migrated = migrate_ast_schema(raw_json)

    if req.commit:
        save_cached_evolution_tree(repo, req.commit, migrated)
        logger.info(f"Evolution AST cached for commit {req.commit}")
    else:
        save_cached_tree(repo, req.file_path, migrated)
        logger.info(f"Static AST generated and cached for {req.file_path}")

    try:
        from domain_models import AgentASTDocument
        doc = AgentASTDocument.model_validate(migrated)
        tree_data = build_tree_data(doc)
        return {"status": "generated", "data": tree_data}
    except Exception as e:
        logger.warning(f"Tree building failed after generation: {e}")
        return {"status": "generated", "data": migrated}


GITHUB_TOKEN: str | None = None


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "AgentLens/1.0"}
    token = GITHUB_TOKEN or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _github_get(url: str) -> dict | list | None:
    try:
        req = Request(url, headers=_github_headers())
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return None
        logger.error(f"GitHub API error {e.code} for {url}: {e.read().decode()}")
        return None
    except Exception as e:
        logger.error(f"GitHub API request failed: {e}")
        return None


def _detect_remote_file_path(owner: str, repo: str) -> str | None:
    for candidate in ["AGENTS.md", "CLAUDE.md"]:
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{candidate}"
            try:
                req = Request(url, headers={"User-Agent": "AgentLens/1.0"})
                with urlopen(req, timeout=15) as resp:
                    if resp.status == 200:
                        return candidate
            except HTTPError:
                continue
            except Exception:
                continue
    return None


WINDOW_SIZE = 10


def _get_commit_file_changes(owner: str, repo: str, sha: str, target_path: str) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    data = _github_get(url)
    if not data or not isinstance(data, dict):
        return 0
    for file_info in data.get("files", []):
        if file_info.get("filename") == target_path:
            return file_info.get("changes", 0)
    return 0


def _fetch_github_file_history(owner: str, repo: str, path: str) -> list[dict] | None:
    all_commits = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?path={path}&per_page=100&page={page}"
        data = _github_get(url)
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        for c in data:
            sha = c.get("sha", "")
            commit_info = c.get("commit", {})
            all_commits.append({
                "sha": sha,
                "date": commit_info.get("author", {}).get("date", ""),
                "message": (commit_info.get("message", "") or "").split("\n")[0]
            })
        if len(data) < 100:
            break
        page += 1

    if not all_commits:
        return None

    all_commits.reverse()

    if len(all_commits) <= WINDOW_SIZE:
        logger.info(f"History has {len(all_commits)} commits (≤{WINDOW_SIZE}), using all.")
        return all_commits

    logger.info(f"Fetching change stats for {len(all_commits)} commits to find best window of {WINDOW_SIZE}...")
    commits_with_changes = []
    for c in all_commits:
        changes = _get_commit_file_changes(owner, repo, c["sha"], path)
        commits_with_changes.append({**c, "changes": changes})

    best_window = []
    max_changes = -1
    for i in range(len(commits_with_changes) - WINDOW_SIZE + 1):
        window = commits_with_changes[i:i + WINDOW_SIZE]
        score = sum(c["changes"] for c in window)
        if score > max_changes:
            max_changes = score
            best_window = window

    logger.info(f"Best window: {WINDOW_SIZE} commits, total changes={max_changes}")
    for c in best_window:
        logger.info(f"  [{c['sha'][:7]}] changes={c['changes']:3d} | {c['date']} | {c['message'][:50]}")
    return best_window


def _download_github_raw(owner: str, repo: str, sha: str, path: str) -> str | None:
    urls = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}",
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}",
    ]
    for url in urls:
        try:
            req = Request(url, headers={"User-Agent": "AgentLens/1.0"})
            with urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except HTTPError:
            continue
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
    return None


def _parse_owner_repo(repo_name: str) -> tuple[str, str] | None:
    if "_" not in repo_name:
        return None
    idx = repo_name.index("_")
    return repo_name[:idx], repo_name[idx + 1:]


def _fetch_git_history(file_path: Path) -> list | None:
    repo_name = file_path.stem
    parsed = _parse_owner_repo(repo_name)
    if not parsed:
        logger.error(f"Cannot parse owner/repo from filename: {repo_name}")
        return None

    owner, gh_repo = parsed
    remote_path = _detect_remote_file_path(owner, gh_repo)
    if not remote_path:
        logger.error(f"Cannot detect remote file path (AGENTS.md/CLAUDE.md) for {owner}/{gh_repo}")
        return None

    logger.info(f"Fetching GitHub history: {owner}/{gh_repo}/{remote_path}")
    history = _fetch_github_file_history(owner, gh_repo, remote_path)
    if not history:
        logger.error(f"No commits found for {owner}/{gh_repo}/{remote_path}")
        return None

    logger.info(f"Found {len(history)} commits for {owner}/{gh_repo}/{remote_path}")
    return history


def _read_file_at_commit(file_path: Path, commit: str) -> str | None:
    repo_name = file_path.stem
    parsed = _parse_owner_repo(repo_name)
    if not parsed:
        return None

    owner, gh_repo = parsed
    remote_path = _detect_remote_file_path(owner, gh_repo)
    if not remote_path:
        return None

    logger.info(f"Downloading raw from GitHub: {owner}/{gh_repo}/{commit}/{remote_path}")
    content = _download_github_raw(owner, gh_repo, commit, remote_path)
    if content:
        return content

    logger.warning(f"Falling back to main branch for {owner}/{gh_repo}/{remote_path}")
    return _download_github_raw(owner, gh_repo, "main", remote_path)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("AGENTLENS_PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
