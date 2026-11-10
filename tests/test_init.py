"""Tests for setting up the integration and the MQTT client lifecycle."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
import json
import logging
from typing import Any
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.mec_meter_emulator import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

BASE_CONFIG: dict[str, Any] = {
    "broker": "broker.example.com",
    "port": 8883,
    "username": "user",
    "password": "secret",
    "topic": "prefix",
    "client_id": "client-1",
    "update_interval": 30,
    "templates": {
        "soc": "{{ states('sensor.soc') }}",
        "grid": "{{ states('sensor.grid') }}",
    },
}


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Replace the paho MQTT client with a mock."""
    with patch(
        "custom_components.mec_meter_emulator.mqtt.Client", autospec=True
    ) as client_cls:
        client = client_cls.return_value
        client.publish.return_value.rc = mqtt.MQTT_ERR_SUCCESS
        yield client_cls


async def _setup(hass: HomeAssistant, **overrides: Any) -> bool:
    result = await async_setup_component(
        hass, DOMAIN, {DOMAIN: {**BASE_CONFIG, **overrides}}
    )
    await hass.async_block_till_done()
    return result


async def _advance(hass: HomeAssistant, seconds: int = 30) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_setup_configures_client(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """The client uses the v2 API, credentials, TLS and a background connect."""
    assert await _setup(hass)

    mock_client.assert_called_once_with(
        mqtt.CallbackAPIVersion.VERSION2, client_id="client-1"
    )
    client = mock_client.return_value
    client.username_pw_set.assert_called_once_with("user", "secret")
    client.tls_set_context.assert_called_once()
    client.connect_async.assert_called_once_with("broker.example.com", 8883)
    client.connect.assert_not_called()
    client.loop_start.assert_called_once()


@pytest.mark.parametrize("interval", [0, 4, "abc"])
async def test_setup_rejects_invalid_interval(
    hass: HomeAssistant, mock_client: MagicMock, interval: Any
) -> None:
    """Intervals below 5 seconds or non-numbers fail config validation."""
    assert not await _setup(hass, update_interval=interval)
    mock_client.assert_not_called()


async def test_update_interval_defaults_to_60(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """update_interval is optional and defaults to 60 seconds."""
    hass.states.async_set("sensor.soc", "50")
    config = {k: v for k, v in BASE_CONFIG.items() if k != "update_interval"}
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()
    publish = mock_client.return_value.publish

    await _advance(hass, 30)
    publish.assert_not_called()

    await _advance(hass, 60)
    publish.assert_called_once()


async def test_publishes_payload_on_interval(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Each interval publishes the rendered values to <topic>/solar-api."""
    hass.states.async_set("sensor.soc", "55.5")
    hass.states.async_set("sensor.grid", "-1200")
    assert await _setup(hass)

    await _advance(hass)

    publish = mock_client.return_value.publish
    publish.assert_called_once()
    topic, raw = publish.call_args.args
    assert topic == "prefix/solar-api"
    data = json.loads(raw)
    assert data["qos"] == "good"
    assert data["payload"]["inv"] == {"1": {"soc": 55.5}}
    assert data["payload"]["sit"] == {"grid": -1200.0}


async def test_no_publish_without_valid_values(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Nothing is published when every template is unavailable."""
    hass.states.async_set("sensor.soc", "unavailable")
    hass.states.async_set("sensor.grid", "unknown")
    assert await _setup(hass)

    await _advance(hass)

    mock_client.return_value.publish.assert_not_called()


async def test_failed_publish_is_logged(
    hass: HomeAssistant,
    mock_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A publish rejected by paho (e.g. while disconnected) is logged."""
    caplog.set_level(logging.DEBUG, logger="custom_components.mec_meter_emulator")
    mock_client.return_value.publish.return_value.rc = mqtt.MQTT_ERR_NO_CONN
    hass.states.async_set("sensor.soc", "50")
    assert await _setup(hass)

    await _advance(hass)

    assert "Publish failed" in caplog.text


async def test_stop_disconnects_client(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Home Assistant shutdown stops publishing and disconnects the client."""
    hass.states.async_set("sensor.soc", "50")
    assert await _setup(hass)
    client = mock_client.return_value

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    client.disconnect.assert_called_once()
    client.loop_stop.assert_called_once()

    await _advance(hass)
    client.publish.assert_not_called()
