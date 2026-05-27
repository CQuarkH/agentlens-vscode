import json
import hashlib
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

AGENTLENS_CACHE_ROOT = Path(os.environ.get("AGENTLENS_CACHE_ROOT", str(Path.home() / ".agentlens")))


def _repo_cache_dir(repo: str) -> Path:
    safe = repo.replace("/", "_").replace("\\", "_")
    return AGENTLENS_CACHE_ROOT / safe


def _tree_cache_path(repo: str, file_path: str) -> Path:
    name = Path(file_path).name
    json_name = name.rsplit(".", 1)[0] + ".json"
    return _repo_cache_dir(repo) / "trees" / json_name


def _evolution_tree_path(repo: str, sha: str) -> Path:
    return _repo_cache_dir(repo) / "evolution" / "trees" / f"{sha}.json"


def _file_history_path(repo: str) -> Path:
    return _repo_cache_dir(repo) / "evolution" / "file_history.json"


def get_cached_tree(repo: str, file_path: str) -> dict | None:
    path = _tree_cache_path(repo, file_path)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read cached tree {path}: {e}")
    return None


def save_cached_tree(repo: str, file_path: str, data: dict):
    path = _tree_cache_path(repo, file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Cached tree saved: {path}")


def get_cached_evolution_tree(repo: str, sha: str) -> dict | None:
    path = _evolution_tree_path(repo, sha)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read evolution tree {path}: {e}")
    return None


def save_cached_evolution_tree(repo: str, sha: str, data: dict):
    path = _evolution_tree_path(repo, sha)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_file_history(repo: str) -> list | None:
    path = _file_history_path(repo)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read file history {path}: {e}")
    return None


def save_file_history(repo: str, history: list):
    path = _file_history_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def get_robust_id(text: str) -> str:
    if not text:
        return "empty"
    normalized = "".join(c for c in text.lower() if c.isalnum() or c.isspace())
    normalized = " ".join(normalized.split())
    signature = normalized[:40]
    return hashlib.md5(signature.encode("utf-8")).hexdigest()[:10]
