"""Tests for line selection."""

from unittest.mock import AsyncMock, patch

from custom_components.ha_departures.config_flow import (
    DeparturesOptionsFlowHandler,
    _extract_lines_from_stop_times,
    _fetch_lines,
)
from custom_components.ha_departures.const import CONF_AVAILABLE_LINES, CONF_LINES, DOMAIN
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _stop_time(headsign, direction="1", route="rer-b", name="B", terminus=None):
    return {
        "routeId": route,
        "directionId": direction,
        "routeShortName": name,
        "headsign": headsign,
        "tripTo": {"name": terminus} if terminus else None,
        "mode": "REGIONAL_RAIL",
    }


def test_multiple_missions_are_one_line_per_direction():
    """A changing trip headsign must not label the whole line."""
    data = {
        "stopTimes": [
            _stop_time("LOVE", terminus="Orsay - Ville"),
            _stop_time("PPIT", terminus="Saint-Rémy-lès-Chevreuse"),
            _stop_time("EPOI", direction="0", terminus="Aéroport CDG"),
            _stop_time("EPOI", direction="0", terminus="Aéroport CDG"),
            _stop_time("Central", route="other", name="C", terminus="Cité"),
        ]
    }

    lines = _extract_lines_from_stop_times(data)
    labels = {(line.route_id, line.direction_id): line.head_sign for line in lines}

    assert labels == {
        ("rer-b", "1"): "Orsay - Ville / Saint-Rémy-lès-Chevreuse",
        ("rer-b", "0"): "Aéroport CDG",
        ("other", "1"): "Cité",
    }
    assert [line.head_sign for line in _extract_lines_from_stop_times(data, False)] == [
        "Orsay - Ville",
        "Saint-Rémy-lès-Chevreuse",
        "Aéroport CDG",
        "Aéroport CDG",
        "Cité",
    ]


def test_missing_terminus_uses_readable_fallback():
    """Missing API destination data is not replaced by a trip headsign."""
    data = {"stopTimes": [_stop_time("LOVE", terminus=None)]}

    assert _extract_lines_from_stop_times(data)[0].head_sign == "Terminus inconnu"


async def test_missions_from_different_stops_are_grouped_together():
    """Grouping happens after all stop responses are collected."""
    responses = [
        {"stopTimes": [_stop_time("LOVE", terminus="Orsay - Ville")]},
        {
            "stopTimes": [
                _stop_time("PPIT", terminus="Saint-Rémy-lès-Chevreuse")
            ]
        },
    ]
    with patch(
        "custom_components.ha_departures.config_flow._send_api_request",
        new_callable=AsyncMock,
        side_effect=responses,
    ):
        lines = await _fetch_lines(["stop-1", "stop-2"])

    assert len(lines) == 1
    assert lines[0].route_short_name == "B"
    assert lines[0].head_sign == "Orsay - Ville / Saint-Rémy-lès-Chevreuse"


async def test_options_flow_refreshes_selected_terminus(hass):
    """An existing selection adopts the refreshed terminus label."""
    old_line = {
        "route_id": "rer-b",
        "direction_id": "1",
        "head_sign": "Direction 1",
        "route_short_name": "B",
        "transport_mode": "REGIONAL_RAIL",
    }
    new_line = {**old_line, "head_sign": "Orsay - Ville"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Hub",
        data={CONF_AVAILABLE_LINES: [new_line]},
        options={CONF_LINES: [old_line]},
    )
    entry.add_to_hass(hass)

    result = await DeparturesOptionsFlowHandler(entry).async_step_init(
        {"lines": ["rer-b---1"]}
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_LINES] == [new_line]
