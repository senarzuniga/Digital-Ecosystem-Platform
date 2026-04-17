"""
OPC-UA Connector — reads node values from OPC-UA servers and maps them
to the platform telemetry schema.

Requires:  pip install asyncua
Enable:    Set OPCUA_ENABLED=true + OPCUA_ENDPOINT in .env

Node mapping example (per asset, in connector_config JSON on Asset model):
    {
        "temperature": "ns=2;i=1001",
        "vibration":   "ns=2;i=1002",
        "power_kw":    "ns=2;i=1003"
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, List, Optional

from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OpcUaReading:
    def __init__(self, node_id: str, metric: str, value: float):
        self.node_id = node_id
        self.metric  = metric
        self.value   = value


class OpcUaConnector:
    """
    Polls OPC-UA nodes for a list of assets and returns telemetry dicts.

    Usage:
        connector = OpcUaConnector()
        readings  = await connector.read_asset(asset_id, node_mapping)
    """

    def __init__(self) -> None:
        self._client = None

    async def connect(self) -> None:
        if not settings.OPCUA_ENABLED:
            logger.info("OPC-UA connector disabled (OPCUA_ENABLED=false)")
            return
        try:
            from asyncua import Client
        except ImportError:
            logger.warning("asyncua not installed. Run: pip install asyncua")
            return
        try:
            self._client = Client(url=settings.OPCUA_ENDPOINT)
            await self._client.connect()
            logger.info("OPC-UA connected to %s", settings.OPCUA_ENDPOINT)
        except Exception as exc:
            logger.error("OPC-UA connection failed: %s", exc)
            self._client = None

    async def disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        logger.info("OPC-UA disconnected")

    async def read_asset(
        self, asset_id: str, node_mapping: Dict[str, str]
    ) -> Dict[str, Optional[float]]:
        """
        Read all mapped nodes for an asset.

        Returns: {"temperature": 72.4, "vibration": 1.8, ...}
        """
        if self._client is None:
            logger.debug("OPC-UA not connected; returning empty telemetry for asset %s", asset_id)
            return {}

        readings: Dict[str, Optional[float]] = {}
        for metric, node_id in node_mapping.items():
            try:
                node  = self._client.get_node(node_id)
                value = await node.read_value()
                readings[metric] = float(value)
            except Exception as exc:
                logger.warning("OPC-UA read error for node %s (%s): %s", node_id, metric, exc)
                readings[metric] = None
        return readings

    async def poll_assets(
        self,
        assets: List[dict],  # list of {"asset_id": str, "node_mapping": dict}
        interval_seconds: float = 30.0,
        callback=None,
    ) -> None:
        """Continuously poll assets and call callback(asset_id, readings)."""
        while True:
            for asset in assets:
                readings = await self.read_asset(asset["asset_id"], asset.get("node_mapping", {}))
                if callback and readings:
                    await callback(asset["asset_id"], readings)
            await asyncio.sleep(interval_seconds)
