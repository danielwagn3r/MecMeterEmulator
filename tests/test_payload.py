"""Tests for template rendering and payload building."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.mec_meter_emulator import _build_payload, _render_float
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

NOW = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{{ 42 }}", 42.0),
        ("{{ '-1.5' }}", -1.5),
        ("  12  ", 12.0),
        ("{{ 'unknown' }}", None),
        ("{{ 'unavailable' }}", None),
        ("{{ 'Unavailable' }}", None),
        ("{{ none }}", None),
        ("", None),
    ],
)
async def test_render_float(
    hass: HomeAssistant, template: str, expected: float | None
) -> None:
    """Numeric results are converted, invalid states are skipped."""
    assert _render_float("grid", Template(template, hass)) == expected


async def test_render_float_non_numeric(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-numeric value is skipped with a warning."""
    assert _render_float("pv", Template("{{ 'abc' }}", hass)) is None
    assert "Template 'pv' rendered non-numeric value: 'abc'" in caplog.text


async def test_render_float_template_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A template error is skipped with a warning instead of raising."""
    assert _render_float("ld", Template("{{ 1 / 0 }}", hass)) is None
    assert "Error rendering template 'ld'" in caplog.text


async def test_build_payload(hass: HomeAssistant) -> None:
    """soc goes to the inverter section, all other keys to the site section."""
    hass.states.async_set("sensor.soc", "55.5")
    hass.states.async_set("sensor.grid", "-1200")
    templates = {
        "soc": Template("{{ states('sensor.soc') }}", hass),
        "grid": Template("{{ states('sensor.grid') }}", hass),
    }

    assert _build_payload(templates, NOW) == {
        "timestampDevice": 1794312000000,
        "qos": "good",
        "payload": {
            "inv": {"1": {"soc": 55.5}},
            "sit": {"grid": -1200.0},
            "ts": "2026-11-10T12:00:00+00:00",
        },
    }


async def test_build_payload_skips_invalid_values(hass: HomeAssistant) -> None:
    """Invalid values are left out while valid ones are still sent."""
    hass.states.async_set("sensor.soc", "unavailable")
    hass.states.async_set("sensor.pv", "3000")
    templates = {
        "soc": Template("{{ states('sensor.soc') }}", hass),
        "pv": Template("{{ states('sensor.pv') }}", hass),
    }

    payload = _build_payload(templates, NOW)

    assert payload is not None
    assert payload["payload"]["inv"] == {"1": {}}
    assert payload["payload"]["sit"] == {"pv": 3000.0}


async def test_build_payload_nothing_valid(hass: HomeAssistant) -> None:
    """No payload is built when no template produced a value."""
    hass.states.async_set("sensor.soc", "unknown")
    templates = {"soc": Template("{{ states('sensor.soc') }}", hass)}

    assert _build_payload(templates, NOW) is None
    assert _build_payload({}, NOW) is None
