"""MEC Meter Emulator: publish template values to an MQTT broker in MECMeter format."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import ssl
from typing import Any

import paho.mqtt.client as mqtt
import voluptuous as vol

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mec_meter_emulator"

CONF_BROKER = "broker"
CONF_TOPIC = "topic"
CONF_TEMPLATES = "templates"
CONF_UPDATE_INTERVAL = "update_interval"

INV_KEYS = ("soc",)
SIT_KEYS = ("akk", "grid", "ld", "pv")
INV_NUMBER = "1"
INVALID_STATES = {"", "none", "unknown", "unavailable"}

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_BROKER): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_TOPIC): cv.string,
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Optional(CONF_TEMPLATES, default={}): {
                    vol.Optional(key): cv.template for key in (*INV_KEYS, *SIT_KEYS)
                },
                vol.Optional(CONF_UPDATE_INTERVAL, default=60): vol.All(
                    vol.Coerce(int), vol.Range(min=5)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _render_float(key: str, template: Template) -> float | None:
    """Render a template to a float, or None if the value is not usable."""
    try:
        rendered = template.async_render(parse_result=False)
    except TemplateError as err:
        _LOGGER.warning("Error rendering template '%s': %s", key, err)
        return None

    value = str(rendered).strip()
    if value.lower() in INVALID_STATES:
        return None
    try:
        return float(value)
    except ValueError:
        _LOGGER.warning("Template '%s' rendered non-numeric value: %r", key, value)
        return None


def _build_payload(
    templates: dict[str, Template], now: datetime
) -> dict[str, Any] | None:
    """Build the MECMeter payload, or None if no template produced a value."""
    inv: dict[str, float] = {}
    sit: dict[str, float] = {}
    for key, template in templates.items():
        if (value := _render_float(key, template)) is None:
            continue
        (inv if key in INV_KEYS else sit)[key] = value

    if not inv and not sit:
        return None

    return {
        "timestampDevice": int(now.timestamp() * 1000),
        "qos": "good",
        "payload": {
            "inv": {INV_NUMBER: inv},
            "sit": sit,
            "ts": now.isoformat(timespec="seconds"),
        },
    }


def _create_client(conf: ConfigType) -> mqtt.Client:
    """Create, configure and start the MQTT client."""
    client = mqtt.Client(client_id=conf[CONF_CLIENT_ID])
    client.username_pw_set(conf[CONF_USERNAME], conf[CONF_PASSWORD])
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.enable_logger(_LOGGER)

    def on_connect(client, userdata, flags, rc) -> None:
        if rc == 0:
            _LOGGER.info("Connected to MQTT broker %s", conf[CONF_BROKER])
        else:
            _LOGGER.error("Failed to connect to MQTT broker: %s", rc)

    client.on_connect = on_connect
    client.connect(conf[CONF_BROKER], conf[CONF_PORT])
    client.loop_start()
    return client


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the MEC Meter Emulator from YAML."""
    conf = config[DOMAIN]
    topic = f"{conf[CONF_TOPIC]}/solar-api"
    templates = conf[CONF_TEMPLATES]

    client = _create_client(conf)

    def _publish(_now: datetime) -> None:
        payload = _build_payload(templates, dt_util.utcnow())
        if payload is None:
            return
        client.publish(topic, json.dumps(payload))

    track_time_interval(
        hass, _publish, timedelta(seconds=conf[CONF_UPDATE_INTERVAL])
    )
    return True
