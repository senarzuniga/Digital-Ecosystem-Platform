"""
MQTT Connector — subscribes to IIoT machine topics and injects telemetry
into the platform data pipeline.

Requires:  pip install asyncio-mqtt paho-mqtt
Enable:    Set MQTT_ENABLED=true + MQTT_BROKER_HOST in .env
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Coroutine, Optional

from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TelemetryCallback = Callable[[str, dict], Coroutine]


class MQTTConnector:
    """
    Async MQTT client wrapper.

    Topic convention:  dep/machines/{company_id}/{asset_id}/telemetry
    Payload example:
        {"temperature": 72.4, "vibration": 1.8, "power_kw": 22.1}
    """

    TELEMETRY_TOPIC_PATTERN = "dep/machines/+/+/telemetry"
    ALERT_TOPIC_PATTERN     = "dep/machines/+/+/alert"

    def __init__(self, on_telemetry: Optional[TelemetryCallback] = None) -> None:
        self._on_telemetry = on_telemetry
        self._client = None
        self._running = False

    async def start(self) -> None:
        if not settings.MQTT_ENABLED:
            logger.info("MQTT connector disabled (MQTT_ENABLED=false)")
            return
        try:
            import asyncio_mqtt as aiomqtt
        except ImportError:
            logger.warning("asyncio-mqtt not installed. Run: pip install asyncio-mqtt")
            return

        self._running = True
        logger.info("Connecting to MQTT broker %s:%d", settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT)

        try:
            async with aiomqtt.Client(
                hostname=settings.MQTT_BROKER_HOST,
                port=settings.MQTT_BROKER_PORT,
                username=settings.MQTT_USERNAME or None,
                password=settings.MQTT_PASSWORD or None,
            ) as client:
                self._client = client
                await client.subscribe(self.TELEMETRY_TOPIC_PATTERN)
                await client.subscribe(self.ALERT_TOPIC_PATTERN)
                logger.info("MQTT subscribed to telemetry and alert topics")
                async for message in client.messages:
                    await self._dispatch(str(message.topic), message.payload)
        except Exception as exc:
            logger.error("MQTT connection error: %s", exc)
        finally:
            self._running = False

    async def _dispatch(self, topic: str, raw_payload: bytes) -> None:
        parts = topic.split("/")
        if len(parts) < 5:
            return
        company_id = parts[2]
        asset_id   = parts[3]
        msg_type   = parts[4]

        try:
            payload = json.loads(raw_payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Invalid MQTT payload on topic %s", topic)
            return

        if msg_type == "telemetry" and self._on_telemetry:
            await self._on_telemetry(asset_id, payload)
            logger.debug("MQTT telemetry dispatched: company=%s asset=%s", company_id, asset_id)

    async def stop(self) -> None:
        self._running = False
        logger.info("MQTT connector stopped")

    @property
    def is_running(self) -> bool:
        return self._running
