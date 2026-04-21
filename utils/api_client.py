"""
API Client for the Streamlit frontend.

Tries to connect to the FastAPI backend (DEP_BACKEND_URL env var, default
http://localhost:8000).  Falls back to mock data transparently when the
backend is not reachable, so the frontend always works in demo mode.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("DEP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API_BASE    = f"{BACKEND_URL}/api/v1"
TIMEOUT     = 5  # seconds — keep UI responsive


def _get(path: str, params: Optional[dict] = None, token: Optional[str] = None) -> Optional[Any]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        logger.debug("Backend not reachable at %s", API_BASE)
        return None
    except requests.exceptions.HTTPError as exc:
        logger.warning("API GET %s → %d", path, exc.response.status_code)
        return None
    except Exception as exc:
        logger.warning("API GET %s error: %s", path, exc)
        return None


def _post(path: str, json: dict, token: Optional[str] = None) -> Optional[Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(f"{API_BASE}{path}", json=json, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as exc:
        logger.warning("API POST %s error: %s", path, exc)
        return None


def _patch(path: str, json: dict, token: Optional[str] = None) -> Optional[Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.patch(f"{API_BASE}{path}", json=json, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("API PATCH %s error: %s", path, exc)
        return None


def login(email: str, password: str) -> Optional[str]:
    """Return access token or None."""
    try:
        r = requests.post(
            f"{API_BASE}/auth/login",
            data={"username": email, "password": password},
            timeout=TIMEOUT,
        )
        if r.ok:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


def is_backend_healthy() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=TIMEOUT)
        return r.ok
    except Exception:
        return False


# ── Assets ────────────────────────────────────────────────────────────────────
def list_assets(company_id: str, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/data/assets", params={"company_id": company_id}, token=token)


def get_telemetry(asset_id: str, limit: int = 96, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get(f"/data/telemetry/{asset_id}", params={"limit": limit}, token=token)


# ── Alerts ────────────────────────────────────────────────────────────────────
def list_alerts(company_id: str, status: Optional[str] = None, token: Optional[str] = None) -> Optional[List[dict]]:
    params: dict = {"company_id": company_id}
    if status:
        params["status"] = status
    return _get("/alerts/", params=params, token=token)


def acknowledge_alert(alert_id: str, token: str) -> Optional[dict]:
    return _patch(f"/alerts/{alert_id}", json={"status": "acknowledged"}, token=token)


# ── Work Orders (CMMS) ────────────────────────────────────────────────────────
def list_work_orders(
    company_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[List[dict]]:
    params: dict = {"company_id": company_id}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority
    return _get("/cmms/work-orders", params=params, token=token)


def create_work_order(data: dict, token: str) -> Optional[dict]:
    return _post("/cmms/work-orders", json=data, token=token)


def update_work_order(wo_id: str, updates: dict, token: str) -> Optional[dict]:
    return _patch(f"/cmms/work-orders/{wo_id}", json=updates, token=token)


# ── Agents ────────────────────────────────────────────────────────────────────
def list_agents(token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/agents/", token=token)


def get_agent_log(limit: int = 50, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/agents/log", params={"limit": limit}, token=token)


# ── Finance ───────────────────────────────────────────────────────────────────
def list_invoices(company_id: str, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/finance/invoices", params={"company_id": company_id}, token=token)


def list_contracts(company_id: str, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/finance/contracts", params={"company_id": company_id}, token=token)


# ── Energy ────────────────────────────────────────────────────────────────────
def get_energy_summary(company_id: str, period: Optional[str] = None, token: Optional[str] = None) -> Optional[dict]:
    params: dict = {"company_id": company_id}
    if period:
        params["period"] = period
    return _get("/energy/summary", params=params, token=token)


def get_energy_recommendations(company_id: str, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/energy/recommendations", params={"company_id": company_id}, token=token)


# ── Users ─────────────────────────────────────────────────────────────────────
def list_users(company_id: Optional[str] = None, token: Optional[str] = None) -> Optional[List[dict]]:
    params: dict = {}
    if company_id:
        params["company_id"] = company_id
    return _get("/users/", params=params, token=token)


def get_me(token: str) -> Optional[dict]:
    return _get("/users/me", token=token)


# ── External Integration ───────────────────────────────────────────────────────
def list_external_clients(token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/external/clients", token=token)


def poll_external_client(client_id: str, token: Optional[str] = None) -> Optional[dict]:
    return _post(f"/external/poll/{client_id}", json={}, token=token)


def list_normalized_events(client_id: str, limit: int = 50, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/external/events", params={"client_id": client_id, "limit": limit}, token=token)


def list_normalized_requests(client_id: str, limit: int = 50, token: Optional[str] = None) -> Optional[List[dict]]:
    return _get("/external/requests", params={"client_id": client_id, "limit": limit}, token=token)
