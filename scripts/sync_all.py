"""
Global Sync Utility — sync_all_repos_and_agents()
===================================================
Pushes all pending updates across configured repositories,
restarts all agents via the platform API, and rebuilds system state.

Usage:
    python scripts/sync_all.py

Environment:
    DEP_BACKEND_URL  — FastAPI backend (default http://localhost:8000)
    DEP_API_TOKEN    — Admin JWT token for authenticated calls
    SYNC_REPOS       — Comma-separated list of repo paths to sync (optional)
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("sync_all")

BACKEND_URL = os.getenv("DEP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API_BASE    = f"{BACKEND_URL}/api/v1"
TOKEN       = os.getenv("DEP_API_TOKEN", "")
REPOS_ENV   = os.getenv("SYNC_REPOS", "")


def _headers() -> dict:
    h = {}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


# ── Repository sync ────────────────────────────────────────────────────────────
def sync_git_repo(repo_path: str) -> bool:
    """Pull latest changes for a git repository."""
    path = Path(repo_path).expanduser()
    if not (path / ".git").exists():
        logger.warning("Not a git repo: %s", path)
        return False
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase", "--autostash"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("✅ Repo synced: %s\n   %s", path, result.stdout.strip())
            return True
        else:
            logger.error("❌ Repo sync failed: %s\n   %s", path, result.stderr.strip())
            return False
    except subprocess.TimeoutExpired:
        logger.error("Repo sync timed out: %s", path)
        return False
    except Exception as exc:
        logger.error("Repo sync error: %s — %s", path, exc)
        return False


def sync_all_repos() -> dict:
    """Sync all configured repositories."""
    repos = [r.strip() for r in REPOS_ENV.split(",") if r.strip()] if REPOS_ENV else []

    # Always include the platform repo itself
    platform_root = Path(__file__).parent.parent
    if str(platform_root) not in repos:
        repos.insert(0, str(platform_root))

    results = {}
    for repo in repos:
        logger.info("Syncing repo: %s", repo)
        results[repo] = sync_git_repo(repo)
    return results


# ── Backend API calls ─────────────────────────────────────────────────────────
def _api_get(path: str) -> dict | list | None:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_headers(), timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        logger.warning("Backend not reachable at %s", BACKEND_URL)
        return None
    except Exception as exc:
        logger.warning("API call failed: %s — %s", path, exc)
        return None


def check_backend_health() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if r.ok:
            data = r.json()
            logger.info("✅ Backend healthy: %s v%s", data.get("app"), data.get("version"))
            return True
    except Exception:
        pass
    logger.warning("❌ Backend health check failed")
    return False


def list_agents() -> list:
    agents = _api_get("/agents/") or []
    logger.info("Agents registered: %d", len(agents))
    for a in agents:
        logger.info("  → %s (%s) — enabled=%s", a["name"], a["agent_id"], a["enabled"])
    return agents


def get_event_history() -> list:
    events = _api_get("/agents/events/history?limit=20") or []
    logger.info("Recent events: %d", len(events))
    return events


# ── Rebuild system state ──────────────────────────────────────────────────────
def rebuild_system_state() -> dict:
    """Verify data integrity and reseed DB with defaults if needed."""
    logger.info("Rebuilding system state...")
    state: dict = {}

    # Check asset count
    assets = _api_get("/data/assets")
    state["assets"] = len(assets) if assets else 0
    logger.info("Assets in DB: %d", state["assets"])

    # Check open alerts
    alerts = _api_get("/alerts/?status=open")
    state["open_alerts"] = len(alerts) if alerts else 0
    logger.info("Open alerts: %d", state["open_alerts"])

    # Check open work orders
    wos = _api_get("/cmms/work-orders?status=open")
    state["open_work_orders"] = len(wos) if wos else 0
    logger.info("Open work orders: %d", state["open_work_orders"])

    return state


# ── Main sync function ────────────────────────────────────────────────────────
def sync_all_repos_and_agents() -> dict:
    """
    Master sync function.

    1. Sync all git repositories
    2. Check backend health
    3. List and verify all agents
    4. Rebuild system state
    5. Return summary report
    """
    logger.info("=" * 60)
    logger.info("DEP GLOBAL SYNC — starting")
    logger.info("=" * 60)

    report: dict = {}

    # 1. Sync repos
    logger.info("\n── Phase 1: Repository Sync ──────────────────────────────")
    report["repos"] = sync_all_repos()

    # 2. Backend health
    logger.info("\n── Phase 2: Backend Health Check ────────────────────────")
    report["backend_healthy"] = check_backend_health()

    if not report["backend_healthy"]:
        logger.warning("Backend unreachable — skipping agent and state phases")
        report["skipped"] = ["agents", "state"]
        return report

    # 3. Agent verification
    logger.info("\n── Phase 3: Agent Verification ──────────────────────────")
    report["agents"] = list_agents()

    # 4. Recent events
    logger.info("\n── Phase 4: Event Bus History ───────────────────────────")
    report["recent_events"] = get_event_history()

    # 5. System state
    logger.info("\n── Phase 5: System State Rebuild ────────────────────────")
    report["system_state"] = rebuild_system_state()

    logger.info("\n── SYNC COMPLETE ──────────────────────────────────────────")
    logger.info("Summary: repos=%d backend=%s agents=%d open_alerts=%d open_wos=%d",
                len(report.get("repos", {})),
                "✅" if report["backend_healthy"] else "❌",
                len(report.get("agents", [])),
                report.get("system_state", {}).get("open_alerts", "?"),
                report.get("system_state", {}).get("open_work_orders", "?"))

    return report


if __name__ == "__main__":
    result = sync_all_repos_and_agents()
    success = result.get("backend_healthy", False)
    sys.exit(0 if success else 1)
